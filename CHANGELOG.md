# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1] - 2026-03-20

### Metadata
- Updated PyPI package metadata (email: DETONG.KEJI@GMAIL.COM).
- Added PyPI version badge to README.

## [0.1.0] - 2026-03-20

### Added
- **Core Engine:** Deterministic rule-based extraction pipeline (Fetch -> Discover -> Parse -> Classify -> Merge).
- **Classification:** "Hospital", "University", "Government", "NonProfit", "InternationalOrg" taxonomy with Bayesian fallback.
- **Microservices:** Dockerized `extractor-service` (sync) and `job-service` (async batch).
- **CLI:** `orga parse` and `orga parse-batch` commands.
- **Governance:** `ClassificationAggregator` for page-weighting and noise suppression.

### Fixed
- Stabilized `AddressParser` against `NoneType` crashes on malformed HTML.
- Implemented strict isolation for "partially parsed" address strings.
- Fixed `parse-batch` CLI to support optional output files and pretty printing.

### Security
- Enforced strict dependency pinning.
- Removed all hardcoded test credentials or placeholders.
