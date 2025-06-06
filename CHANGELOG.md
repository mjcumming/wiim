# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.


## [0.0.13] - 2025-06-06

### Fixed

- Fixed missing `release.yml` workflow for manual tag-based releases
- Auto-release workflow properly enabled and monitoring manifest.json changes
- Both workflows now create proper HACS-compatible ZIP structure

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

## [0.0.5] - 2025-06-06

### Changed

- Bumped version for HACS release.

### Fixed

- Coordinator typing clean-up to satisfy mypy.

## [0.0.6] - 2025-06-06

### Fixed

- Ensure release ZIP structure (`wiim/` at archive root) so HACS extracts into `custom_components/wiim` and Home Assistant can load the integration, eliminating "Integration 'wiim' not found" startup error.
- No functional code changes.

## [0.0.7] - 2025-06-06

### Fixed

- Release workflows now package `custom_components/wiim/` path inside ZIP, matching HACS expectations.
- Version bump to trigger re-release.

## [0.0.8] - 2025-06-06

### Changed

- Updated `codeowners` to `@mjcumming` so HACS shows correct maintainer.

## [0.0.9] - 2025-06-06

### Fixed

- Release asset now includes LICENSE and README at root so license badge renders correctly in HACS.

## [0.0.10] - 2025-06-06

### Changed

- Disabled auto-release workflow; releases now occur only via manual Git tag (`release.yml`).
- No code changes.

## [0.0.11] - 2025-06-06

### Fixed

- README license badge now points to absolute GitHub URL so it displays correctly inside Home Assistant UI.

## [0.0.12] - 2025-06-06

### Maintenance

- No functional changes; tagged to align latest metadata and disable auto-release workflow.
