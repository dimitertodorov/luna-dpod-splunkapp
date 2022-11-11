param(
    $SplunkAppFullName = "TA-luna-hsm-audit-logger",
    $GitTagName = $null
)

task GetVersion {
    $ManifestProps = ((Get-Content -Raw "./$SplunkAppFullName/app.manifest") | ConvertFrom-JSON)
    $AobMetaProps = ((Get-Content -Raw "./$SplunkAppFullName/TA-luna-hsm-audit-logger.aob_meta") | ConvertFrom-JSON)
    $Script:AppVersion = $ManifestProps.info.id.version
    $Script:AobMetaVersion = $AobMetaProps.basic_builder.version
    $AppConfVersion = (Select-String -Path "./$SplunkAppFullName/default/app.conf" -Pattern "^version = ").Line
    $AppConfVersion = $AppConfVersion -replace "version|\s|=", ""

    assert ($AppConfVersion -eq $AppVersion) "Version in app.conf ($AppConfVersion) does not match manifest version ($AppVersion)"
    assert ($AobMetaVersion -eq $AppVersion) "Version in TA-luna-hsm-audit-logger.aob_meta ($AobMetaVersion) does not match manifest version ($AppVersion)"
    
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

task UpdateAobMetaCode {
    $AobMetaProps = ((Get-Content -Raw "./$SplunkAppFullName/TA-luna-hsm-audit-logger.aob_meta") | ConvertFrom-JSON -Depth 99 )
    $CodeContents = (Get-Content -Raw "$SplunkAppFullName/bin/input_module_luna_hsm_audit_log.py")
    $AobMetaProps.data_input_builder.datainputs[0].code = $CodeContents

    ## Update Logos for AOB
    $SmallIconBase64 = [convert]::ToBase64String((get-content "$SplunkAppFullName/static/appIcon.png" -AsByteStream))
    $LargeIconBase64 = [convert]::ToBase64String((get-content "$SplunkAppFullName/static/appIcon_2x.png" -AsByteStream))
    
    $AobMetaProps.basic_builder.large_icon = $LargeIconBase64
    $AobMetaProps.basic_builder.small_icon = $SmallIconBase64

    $AobMetaProps | ConvertTo-Json -Depth 99 -Compress | Out-File -FilePath "./$SplunkAppFullName/TA-luna-hsm-audit-logger.aob_meta"
}

task BuildSplunkAppTgz GetVersion, UpdateAobMetaCode, {
    Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
    exec { tar -czf "./$PackageFileName" "$SplunkAppFullName" }
}