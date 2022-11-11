# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.0.2] - 2022-11-11
### Fixed
- Fixed reference to 'releaseNotes.text' in app.manifest due to SplunkBase verification Failure 
- Updated Build script to verify version matches in app.manifest, globalConfig.json, and aob_meta
- Updated Build script to update aob_meta file on TGZ build

## [1.0.1] - 2022-11-10
### Changed
- Added client_id to event output
- Added better error handling
