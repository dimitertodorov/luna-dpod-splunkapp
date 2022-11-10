param(
    $SplunkAppFullName = "TA-luna-hsm-audit-logger",
    $GitTagName = $null
)

task GetVersion {
    $ManifestProps = ((Get-Content -Raw "./$SplunkAppFullName/app.manifest") | ConvertFrom-JSON)
    $Script:AppVersion = $ManifestProps.info.id.version
    $AppConfVersion = (Select-String -Path "./$SplunkAppFullName/default/app.conf" -Pattern "^version = ").Line
    $AppConfVersion = $AppConfVersion -replace "version|\s|=", ""
    assert ($AppConfVersion -eq $AppVersion) "Version in app.conf ($AppConfVersion) does not match manifest version ($AppVersion)"
    $Script:PackageFileName = "$($SplunkAppFullName)-$($AppVersion).tar.gz"
}

task ValidateGitVersionMatch GetVersion, {
    if ($GitTagName) {
        $GitTagName = $GitTagName -replace "v", ""
        assert ( $AppVersion -eq $GitTagName ) "GitTag Version $GitTagName does not match manifest version ($AppVersion)"
    }
    else {
        throw "GitTagName not Specified. Exiting"
        exit 1
    }
}

task BuildSplunkAppTgz GetVersion, {
    Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
    exec { tar -czf "./$PackageFileName" "$SplunkAppFullName" }
}