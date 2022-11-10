# Luna HSM Splunk App

## Background
This SplunkApp was developed to collect audit logs from Thales DPoD.

Logs are collected from the DPoD API using a python script, and logged to Splunk directly via the internal event writer.

## Code Layout
**TA-luna-hsm-audit-logger**
Contains SplunkApp package for deployment. Must be GZipped before deployments. 
Important File(s)
* input_module_luna_hsm_audit_log.py - Contains all logic for interacting with DPoD API and Splunk.

**test**
Contains scripts and collateral for testing the splunk app logic outside of a Splunk installation. Helpers have been stubbed in.
* run_app_local.py - Script for testing the input module. Will not actually 
* test_config.json - Contains settings for testing (e.g. DPoD connection details). See test_config.sample.json for structure

## TODO
* Create build/deploy scripts
* Add testing framework

### Links

* https://www.thalesdocs.com/dpod/api/audit_query/index.html
* https://data-protection-updates.gemalto.com/2022/07/07/audit-logging-api-now-available-in-data-protection-on-demand-dpod/


This is an add-on powered by the Splunk Add-on Builder.
# Binary File Declaration
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/pvectorc.cpython-37m-x86_64-linux-gnu.so: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/gui-arm64.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/gui-64.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/cli-64.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/cli.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/cli-arm64.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/gui.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/gui-32.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/setuptools/cli-32.exe: this file does not require any source code
/opt/splunk/var/data/tabuilder/package/TA-luna-hsm-audit-logger/bin/ta_luna_hsm_audit_logger/aob_py3/markupsafe/_speedups.cpython-37m-x86_64-linux-gnu.so: this file does not require any source code
