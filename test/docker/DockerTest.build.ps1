param(
    $SplunkContainerName = "splunktest001",
    $MaxWaitSeconds = 120,
    $SplunkHome = "/opt/splunk",
    $SplunkETC = "/opt/splunk/etc",
    $SplunkStartArgs = "--accept-license",
    $SplunkEnableListen = "9997",
    $SplunkAdd = "tcp 1514",
    $SplunkPassword = "newPassword",
    $SplunkHostname = "idx-example.splunkcloud.com",
    $SplunkAppName = "TA-luna-hsm-audit-logger",
    $SplunkAppsDir = "/opt/splunk/etc/apps",
    $SplunkDockerImage = "splunk/splunk:9.0",
    $SplunkDockerAppPort = "8098",
    $SplunkDockerApiPort = "8090",
    $DockerNetworkName = "splunktestnet",
    $MockServerContainerName = "lunamock001",
    $MockServerHostname = "lunatest.mock",
    $MockServerPort = "8084",
    $MockServerClientId = "643e7442-4ca3-49a2-9cd3-41f9352b4138",
    $MockServerClientSecret = "securepassword",
    $MockServerAggregateEventTypes = "LUNA_DECRYPT_SINGLEPART,LUNA_VERIFY_SINGLEPART"
)

task ResolveVariables {
    ## Mock Luna API Settings
    $Script:MockPythonServerPath = (Resolve-Path -Path "../python/mock_luna_server").Path
    $Script:MockPythonServerPath = ($MockPythonServerPath -replace "\\", "/")
    $Script:MockPythonServerFile = "run_mock_dpod.py"
    $Script:SplunkAppRoot = (Resolve-Path "../../$SplunkAppName")
    $Script:MockServerUri = "https://$($MockServerHostname):$($MocKServerPort)"
    $Script:MockServerSslCertificate = "$MockPythonServerPath/ssl/lunatest.mock.pem"
    $Script:LocalApiUri = "https://localhost:$($SplunkDockerApiPort)"
    ## pscredential Object for REST Calls
    [securestring]$SecureSplunkPassword = ConvertTo-SecureString $SplunkPassword -AsPlainText -Force
    [pscredential]$Script:SplunkCreds = New-Object System.Management.Automation.PSCredential ("admin", $SecureSplunkPassword)
}

task CleanupDocker {
    exec { docker rm -f $SplunkContainerName 2> $null }
    exec { docker rm -f $MockServerContainerName 2> $null }
}

task CreateDockerNetworks {
    ## Create Testing Network
    if ($(docker network inspect $DockerNetworkName) -eq "[]") {
        exec { docker network create $DockerNetworkName }
    }
}

task CreateDockerLunaMockContainer ResolveVariables, CreateDockerNetworks, {
    ## Start Luna Mock Server
    exec { 
        docker run -d --name $MockServerContainerName `
            --hostname $MockServerHostname `
            --network $DockerNetworkName `
            -p 9084:8084 `
            -v ${MockPythonServerPath}:/lunamock -w /lunamock `
            python:3 `
            python $MockPythonServerFile --port $MockServerPort --client_id "$MockServerClientId" --client_secret "$MockServerClientSecret"
    }
}

task CreateDockerSplunkContainer CreateDockerNetworks, {
    $AppPortRef = "$($SplunkDockerAppPort):8000"
    $ApiPortRef = "$($SplunkDockerApiPort):8089"
    exec {
        ## Start Splunk Test Container
        docker run -d `
            --name $SplunkContainerName `
            --network $DockerNetworkName `
            --hostname $SplunkHostname `
            --env SPLUNK_HOME="$SplunkHome" `
            --env SPLUNK_ETC="$SplunkETC" `
            --env SPLUNK_START_ARGS="$SplunkStartArgs" `
            --env SPLUNK_ENABLE_LISTEN="$SplunkEnableListen" `
            --env SPLUNK_ADD="$SplunkAdd" `
            --env SPLUNK_PASSWORD="$SplunkPassword" `
            --env SSL_CERT_FILE="/sslverify/lunatest.mock.pem" `
            --user root `
            -p $AppPortRef `
            -p $ApiPortRef `
            $SplunkDockerImage
    }
}

task AssertDockerContainersExist {
    $SplunkContainerStatus = (docker ps --filter "name=$SplunkContainerName" --format "{{.Status}}")
    assert ( -not [string]::IsNullOrEmpty($SplunkContainerStatus))
    $MockContainerStatus = (docker ps --filter "name=$MockServerContainerName" --format "{{.Status}}")
    assert ( -not [string]::IsNullOrEmpty($MockContainerStatus))
}

task CopySplunkAppFilesToDocker ResolveVariables, AssertDockerContainersExist, {
    Write-Output "Copying SplunkAppFiles"
    exec {
        docker exec $SplunkContainerName bash -c "mkdir -p -m 777 /opt/splunk/etc/apps && mkdir -p -m 777 /output && mkdir -p -m 777 /sslverify"
        docker exec $SplunkContainerName bash -c "touch /opt/splunk/etc/.ui_login"
    }
    exec {
        docker cp $MockServerSslCertificate "$($SplunkContainerName):/sslverify/"
        docker cp $SplunkAppRoot "$($SplunkContainerName):$($SplunkAppsDir)/$($SplunkAppName)"
    }
}

task CheckDockerSplunkHealth AssertDockerContainersExist, {
    $LoopCounter = 0
    $ContainerHealth = "starting"
    While (($LoopCounter -lt $MaxWaitSeconds) -and ($ContainerHealth -ilike "*starting*")) {
        $ContainerHealth = docker ps --filter "name=$($SplunkContainerName)" --format "{{.Status}}"
        $LoopCounter += 1
        $ProgressParameters = @{
            Activity        = 'Waiting for Splunk to be Available'
            Status          = "Progress-> $ContainerHealth"
            PercentComplete = ($LoopCounter / $MaxWaitSeconds * 100)
        }
        Write-Progress @ProgressParameters
        Start-Sleep -Seconds 1
    }
    assert { (docker ps --filter "name=$($SplunkContainerName)" --format "{{.Status}}") -ne "" }     
}




task CheckDockerKVStoreHealth CheckDockerSplunkHealth, ResolveVariables, {
    # Wait for KV Store to be available
    $LoopCounter = 0
    $SplunkKVStoreStatus = ""
    While (($LoopCounter -lt $MaxWaitSeconds) -and (-not ($SplunkKVStoreStatus -eq 'ready'))) {
        $RequestSplat = @{
            Method               = "GET"
            Uri                  = "$($LocalApiUri)/services/server/info"
            SkipCertificateCheck = $true
            Credential           = $SplunkCreds
        }
        try {
            $SplunkServerInfo = Invoke-RestMethod @RequestSplat
            $SplunkKVStoreStatus = ($SplunkServerInfo.content.dict.key | Where-Object { $_.name -eq 'kvStoreStatus' }).'#text'   
        }
        catch {
            $SplunkKVStoreStatus = "Error $($_.Exception)"
        }
        $LoopCounter += 1
        $ProgressParameters = @{
            Activity        = 'Waiting for Splunk KV Store to be Available'
            Status          = "KV Store Status -> $SplunkKVStoreStatus"
            PercentComplete = ($LoopCounter / $MaxWaitSeconds * 100)
        }
        Write-Progress @ProgressParameters
        Start-Sleep -Seconds 1
    }
    assert ($SplunkKVStoreStatus -eq 'ready')
}

task CheckDockerSplunkSearchLunaEvents @{
    Jobs = 'ResolveVariables',
    'AssertDockerContainersExist',
    'CheckDockerSplunkHealth',
    'CheckDockerKVStoreHealth', 
    {
        $SearchQuery = 'search sourcetype="luna_hsm" "status=LUNA_RET_OK"'
        $SearchResults = 0
        $LoopCounter = 0
        $SearchParams = @{
            search        = $SearchQuery
            output_mode   = 'json'
            earliest_time = '-5m'
        }
        While (($SearchResults -eq 0) -and ($LoopCounter -lt $MaxWaitSeconds)) {
            $RequestSplat = @{
                Method               = "POST"
                Body                 = $SearchParams
                Uri                  = "$($LocalApiUri)/services/search/jobs/export"
                SkipCertificateCheck = $true
                Credential           = $SplunkCreds
            }
            $SplunkSearchResults = Invoke-RestMethod @RequestSplat
            $LoopCounter += 1
            $SearchResults = ($SplunkSearchResults -split "\n").Count - 1
            $ProgressParameters = @{
                Activity        = "Searching for Splunk Events - $SearchQuery"
                Status          = "Events Found $SearchResults"
                PercentComplete = ($LoopCounter / $MaxWaitSeconds * 100)
            }
            if ($SearchResults -ne 0) {
                $ProgressParameters.PercentComplete = 100
            }
            Write-Progress @ProgressParameters
            Start-Sleep -Seconds 1
        }
        Write-Output "Splunk Search Completed - $($SearchResults) Events Found"

        assert($SearchResults -gt 0)
    }
}

task RunDockerIntegrationTest @{
    Jobs = "CleanupDocker",
    "CreateDockerLunaMockContainer",
    "CreateDockerSplunkContainer",
    "CopySplunkAppFilesToDocker",
    "CheckDockerSplunkHealth",
    "CheckDockerKVStoreHealth",
    "CreateSplunkAppTestInput",
    "DisableSplunkInstrumentation",
    "CheckDockerSplunkSearchLunaEvents", {
        Write-Output "Testing Successfully Completed"
    }
}

task ReplaceSplunkAppFilesInDocker ResolveVariables, {
    Write-Output "Replacing SplunkAppFiles"
    exec {
        docker exec $SplunkContainerName bash -c "rm -rf  /tmp/$($SplunkAppName)"
        docker cp $SplunkAppRoot "$($SplunkContainerName):/tmp/$($SplunkAppName)"
        docker exec $SplunkContainerName bash -c "cp -rf  /tmp/$($SplunkAppName) $($SplunkAppsDir)"
    }
}

task RestartSplunkDockerServices ResolveVariables, {
    $AppRestartUri = "$($LocalApiUri)/services/server/control/restart"
    $RequestSplat = @{
        Method               = "POST"
        Uri                  = $AppRestartUri
        SkipCertificateCheck = $true
        Credential           = $SplunkCreds
    }
    Invoke-RestMethod @RequestSplat
    Start-Sleep -Seconds 10
}

task DisableSplunkInstrumentation CheckDockerKVStoreHealth, {
    $TelemetryRestUri = "$($LocalApiUri)/servicesNS/nobody/splunk_instrumentation/admin/telemetry/general"
    $TelemetryRequestBody = @{
        sendAnonymizedUsage        = "false"
        sendSupportUsage           = "false"
        sendLicenseUsage           = "false"
        sendAnonymizedWebAnalytics = "false"
        showOptInModal             = 0
        optInVersionAcknowledged   = 4
        output_mode                = "json"
    }
    $RequestSplat = @{
        Method               = "POST"
        Body                 = $TelemetryRequestBody
        Uri                  = $TelemetryRestUri
        SkipCertificateCheck = $true
        Credential           = $SplunkCreds
    }
    $Result = Invoke-RestMethod @RequestSplat
    assert ( $Result.entry.content.showOptInModal -eq $false)
}

task CreateSplunkAppTestInput CheckDockerKVStoreHealth, {
    $AppRestUri = "$($LocalApiUri)/servicesNS/nobody/TA-luna-hsm-audit-logger/TA_luna_hsm_audit_logger_luna_hsm_audit_log"
    $AppRequestBody = @{
        name                    = "TESTHSM"
        interval                = "120"
        index                   = "default"
        authentication_api_base = $MockServerUri
        dpod_api_base           = $MockServerUri
        aggregate_event_types   = $MockServerAggregateEventTypes
        client_id               = $MockServerClientId
        client_secret           = $MockServerClientSecret
        output_mode             = "json"
    }
    $RequestSplat = @{
        Method               = "POST"
        Body                 = $AppRequestBody
        Uri                  = $AppRestUri
        SkipCertificateCheck = $true
        Credential           = $SplunkCreds
    }
    $Result = Invoke-RestMethod @RequestSplat
    assert ( $Result.entry.content.dpod_api_base -eq $MockServerUri )
}

    