# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- MIT License, CONTRIBUTING.md, GitHub issue/PR templates
- Branch protection rulesets for `develop` and `master`
- Repository topics for discoverability

### Changed
- Replaced hardcoded IP addresses with `YOUR_AGATE_IP` placeholder
- Replaced device serial numbers with `XXXXXXXXXXXXXXXXXXXX` placeholder
- Updated `setup.py` email to GitHub noreply address
- Cleaned docs/ and tools/ indexes for public visibility

### Removed
- Internal test results, archive directory, agent configs from tracked files
- 53 one-off tool scripts (9 curated tools remain)
- Internal design docs and proprietary references

## [0.9.0] - 2026-03-16

### Fixed
- **CRITICAL:** WSetPct charge rate calculation used wrong denominator (`WMaxRtg=1000W` instead of `WChaRteMaxRtg=5000W`). Requesting 1200W charge now correctly produces WSetPct=-24% instead of -120%. (DEF-001)
- `actual_power` read-back in `read_full_status()` now uses direction-aware charge/discharge rates
- Success messages display correct rated capacity (5000W) instead of WMaxRtg (1000W)
- "ORPHANED VPP DETECTED" warning downgraded to INFO — WSetEna=1 is normal persistent state (DEF-002)
- Removed EXTENSION REGISTERS section from `--status` output; retained in `--healthcheck` (DEF-003)

### Added
- High-resolution home load from Register 16000 (~1W precision vs 10W from extensions)
- Propagated high-res home load to CLI, standalone tool, and demo
- Base-1 addressing reference in QUIRKS.md
- PICS-driven safety improvements: orphan VPP check, input validation, alarm definitions
- M801/M802 battery model scan — confirmed non-existence on aGate
- Register 15000-15043 correlation analysis

### Changed
- Conflict detection now uses energy context (solar, load, grid) to reduce false positives
- PICS conformance cross-reference updated with vendor submission findings

## [0.8.0] - 2026-03-10

### Added
- Package namespace renamed from `franklinwh` to `franklinwh_modbus` (avoids conflict with Cloud API)
- SunSpec DER sequencing reference documentation
- Comprehensive hardware test guide
- VPP Mode visual reference with mobile app screenshots

### Changed
- CLI restructured to use library imports (`from franklinwh_modbus import ...`)

## [0.7.0] - 2026-03-08

### Added
- Extension register write probing (15507-15509 writability detection)
- Virtual mode specifications (Self-Consumption, Emergency Backup, TOU, Peak Shave, Manual)
- Orchestration and control documentation with sequence diagrams
- Safety controls documentation (10 safety rules)
- Software timeout (watchdog) implementation for VPP commands
- Battery state derivation from DC power (replacing unreliable M713.Sta)

### Fixed
- SoC proximity ramping for charge/discharge near target
- Control conflict detection with aGate native modes

## [0.6.0] - 2026-02-24

### Added
- MQTT publisher with Home Assistant discovery
- TUI monitor (`--monitor`) using Rich library
- TOU schedule support with JSON definitions
- Modbus throttling analysis and rate limiting
- Network scanner for aGate discovery

### Fixed
- Connection stability with threaded status fetching and timeout guards
- MQTT keepalive tuning for persistent sessions

## [0.5.0] - 2026-02-18

### Added
- Initial `FranklinWHController` with pysunspec2 integration
- SunSpec model scanning (Models 1, 701-715)
- Battery charge/discharge via M704 WSetPct/WSetEna
- Extension register reading (15500-15509)
- CLI tool with `--status`, `--charge`, `--discharge`, `--stop`
- Basic alarm monitoring

[Unreleased]: https://github.com/david2069/franklinwh-modbus/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/david2069/franklinwh-modbus/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/david2069/franklinwh-modbus/releases/tag/v0.5.0
