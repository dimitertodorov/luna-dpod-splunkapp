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

### Files of Interest
* ./test/LocalTests.build.ps1 - Contains testing logic for running testing the python code locally against a Mock DPOD API.
* ./test/docker/DockerTest.build.ps1 - Contains tests for testing the SplunkApp in a Dockerized environment complete with Mock DPOD API container

## Local Development
Local development/testing depends on:

* PowerShell Core (Any platform)
* PowerShell Module Invoke-Build
* Docker/Docker Desktop
* Python3

## TODO
* Create build/deploy scripts
* Add testing framework

### Links

* https://www.thalesdocs.com/dpod/api/audit_query/index.html
* https://data-protection-updates.gemalto.com/2022/07/07/audit-logging-api-now-available-in-data-protection-on-demand-dpod/
