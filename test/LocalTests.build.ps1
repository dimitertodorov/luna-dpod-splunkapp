param(
    $MockServerProcess = $null,
    $MockServerPort = 9894
)

task ResolveVariables {
    $Script:TestConfigProps = Get-Content -Raw "./test_config.sample.json" | ConvertFrom-Json
    $TestConfigProps.authentication_api_base = "https://localhost:$MockServerPort"
    $TestConfigProps.dpod_api_base = "https://localhost:$MockServerPort"
    $TestConfigProps | ConvertTo-Json | Out-File "./test_config.json" -Force
    $Script:SslCertPath = (Resolve-Path "python/mock_luna_server/ssl/lunatest.mock.pem").Path
    $env:SSL_CERT_FILE = $Script:SslCertPath
}

task RunMockServer ResolveVariables, {
    $LocalMockServer = (Resolve-Path "python/mock_luna_server/run_mock_dpod.py").Path
    $Script:MockServerProcess = Start-Process -FilePath "python" -ArgumentList $LocalMockServer,"--port",$MockServerPort,"--client_id",$TestConfigProps.client_id,"--client_secret","$($TestConfigProps.client_secret)" -NoNewWindow -PassThru
    Write-Output "Running Mock Server $($Script:MockServerProcess.Id)"
}

task WaitForMockServer {
    $LoopCounter = 0
    $MaxWaitSeconds = 120
    $PingStatus = ""
    While (($LoopCounter -lt $MaxWaitSeconds) -and (-not ($PingStatus -eq "OK"))) {
        $LoopCounter += 1
        $ProgressParameters = @{
            Activity        = 'Waiting for MockServer to be Available'
            Status          = "Progress-> $PingStatus"
            PercentComplete = ($LoopCounter / $MaxWaitSeconds * 100)
        }
        
        try {
            $PingStatus = (Invoke-WebRequest -Uri "https://localhost:$MockServerPort/ping" -Method Get -SkipCertificateCheck).Content
        }
        catch {
            $PingStatus = $_.Exception
        }
        finally {
            $ProgressParameters.Status = "Progress-> $PingStatus"
            Write-Progress @ProgressParameters
        }
        Start-Sleep -Seconds 1
    }
    assert ($PingStatus -eq "OK")
    Write-Output "HTTPS Mock Server is Up"
}

task RunLocalApp WaitForMockServer, ResolveVariables, {
    $LocalRunApp = (Resolve-Path "./python/run_app_local.py").Path
    $LocalRunAppProcess = Start-Process -FilePath "python" -ArgumentList $LocalRunApp -NoNewWindow -Wait -PassThru
    Write-Output "Successfully Ran $($LocalRunAppProcess.Id)"
}

task RunFullTest @{
    Jobs = 'RunMockServer','RunLocalApp',
    {
        if($MockServerProcess){
            Stop-Process -Id $MockServerProcess.Id
        }
    }
}