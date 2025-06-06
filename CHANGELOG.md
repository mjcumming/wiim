# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.

## [0.0.1] - 2025-06-06

### Added

- Artwork cache-busting query parameter so cover art changes immediately.
- New logic to discover unknown master devices automatically.
- Unit-test fixtures adjusted; CI now fully green.

### Changed

- Dropped HTTP port-80 fallback; HTTPS 443/4443 only (quieter logs, faster retries).
- Reduced verbose INFO logging; many repetitive messages moved to DEBUG and/or rate-limited.

### Fixed

- Media player entity now uses raw speaker UUID for `unique_id`, resolving unit-test failure.
- Suppressed "unknow" placeholder values in metadata.

## [0.0.2] - 2025-06-06

### Changed

- Bump version for release automation workflow validation.

## [0.0.3] - 2025-06-06

### Changed

- Re-enabled automatic release and release drafter GitHub workflows.
- Assets are now published as `wiim.zip` to satisfy HACS downloader.
- Version bumped to `0.0.3`.

## [0.0.4] - 2025-06-06

### Fixed

- Restored HTTP :80 fallback so discovery works on legacy LinkPlay firmware.
- Added missing type annotations to eliminate mypy runtime warnings.
- Ignored strict HA typing overrides in `config_flow.py` (#type: ignore).
- Version bumped to `0.0.4`.
