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
    $DockerNetworkName = "splunktestnet",
    $MockServerContainerName = "lunamock001",
    $MockServerHostname = "lunatest.mock"
)

task ResolveVariables {
    ## Mock Luna API Settings
    $Script:MockPythonServerPath = (Resolve-Path -Path "../python/mock_luna_server").Path
    $Script:MockPythonServerPath = ($MockPythonServerPath -replace "\\", "/")
    $Script:MockPythonServerFile = "run_mock_dpod.py"
    $Script:MockLocalInputsConf = (Resolve-Path "./support_files/inputs.conf").Path
    $Script:SplunkAppRoot = (Resolve-Path "../../$SplunkAppName")
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
            python $MockPythonServerFile
    }
}

task CreateDockerSplunkContainer CreateDockerNetworks, {
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
            --user root `
            -p 8098:8000 `
            -p 8090:8089 `
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
        docker exec $SplunkContainerName bash -c "mkdir -p -m 777 /opt/splunk/etc/apps && mkdir -p -m 777 /output"
        docker exec $SplunkContainerName bash -c "touch /opt/splunk/etc/.ui_login"
    }
    exec {
        docker cp $SplunkAppRoot "$($SplunkContainerName):$($SplunkAppsDir)/$($SplunkAppName)"
        docker exec $SplunkContainerName bash -c "mkdir -p $($SplunkAppsDir)/$($SplunkAppName)/local"
        docker exec $SplunkContainerName bash -c "cp -f $($SplunkAppsDir)/$($SplunkAppName)/default/*.conf $($SplunkAppsDir)/$($SplunkAppName)/local/"
        docker cp $MockLocalInputsConf "$($SplunkContainerName):$($SplunkAppsDir)/$($SplunkAppName)/local/"
        docker exec $SplunkContainerName bash -c "chown -hR splunk:splunk $($SplunkAppsDir)/$($SplunkAppName)/local/"
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




task CheckDockerKVStoreHealth CheckDockerSplunkHealth, {
    # Wait for KV Store to be available
    $LoopCounter = 0
    $SplunkKVStoreStatus = ""
    While (($LoopCounter -lt $MaxWaitSeconds) -and (-not ($SplunkKVStoreStatus -eq 'ready'))) {
        $SplunkServerInfo = Invoke-RestMethod -Credential $SplunkCreds `
            -Method GET `
            -Uri "https://localhost:8090/services/server/info" -SkipCertificateCheck
        $SplunkKVStoreStatus = ($SplunkServerInfo.content.dict.key | Where-Object { $_.name -eq 'kvStoreStatus' }).'#text'
        
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
            $SplunkSearchResults = Invoke-RestMethod -Body $SearchParams -Credential $SplunkCreds -Method POST -Uri "https://localhost:8090/services/search/jobs/export" -SkipCertificateCheck
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
    }
}

task RunDockerIntegrationTest @{
    Jobs = "CleanupDocker",
    "CreateDockerLunaMockContainer",
    "CreateDockerSplunkContainer",
    "CopySplunkAppFilesToDocker",
    "CheckDockerSplunkHealth",
    "CheckDockerKVStoreHealth",
    "CheckDockerSplunkSearchLunaEvents", {
        Write-Output "Testing Successfully Completed"
    }
}

    