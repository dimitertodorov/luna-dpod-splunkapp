# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2022-11-16
### Fixed
- Fixed time formatting - DPOD API changed to milisecond precision

### Added
- Logging Role (e.g. CO, SO) with all events

## [1.0.6] - 2022-11-16
### Fixed
- Fixed build issues - App is now at the root level

## [1.0.5] - 2022-11-15
### Fixed
- All remote connections now require HTTPS

### Added
- Logic in input_module_luna_hsm_audit_log.py now uses a wrapper class
- All events will now have the host set to the DPOD API host

## [1.0.3] - 2022-11-11
### Fixed
- Added Binary File Declaration in README.txt 

## [1.0.2] - 2022-11-11
### Fixed
- Fixed reference to 'releaseNotes.text' in app.manifest due to SplunkBase verification Failure 
- Updated Build script to verify version matches in app.manifest, globalConfig.json, and aob_meta
- Updated Build script to update aob_meta file on TGZ build

## [1.0.1] - 2022-11-10
### Changed
- Added client_id to event output
- Added better error handling
