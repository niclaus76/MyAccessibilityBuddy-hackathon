# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Fixed save functionality error handling in webmaster tool - now properly displays error messages from backend HTTPExceptions instead of showing "Unknown error"

## [5.0.0] - 2026-01-19

### Added
- Multi-language support for alt-text generation
- Advanced processing mode with customizable providers and models
- GEO Boost feature for AI search engine optimization
- Translation mode selection (fast vs accurate)
- Progress bar with time estimation
- Session management for web app users
- Report generation and download functionality
- Webmaster tool for single image alt-text generation
- Website accessibility compliance tool for batch processing
- Prompt optimization tool for comparing different prompts
- Administration tool for system configuration

### Changed
- Updated to FastAPI backend architecture
- Improved error handling across all API endpoints
- Enhanced accessibility features for WCAG 2.2 compliance

### Security
- Added session-based isolation for multi-user environments
- Implemented secure cookie handling for authentication

## [4.0.0] - Previous Release

### Added
- Initial multi-provider support (OpenAI, Claude, Ollama, Gemini)
- Basic alt-text generation functionality

---

[Unreleased]: https://github.com/anthropics/Innovate-For-Inclusion---MyAccessibilityBuddy/compare/v5.0.0...HEAD
[5.0.0]: https://github.com/anthropics/Innovate-For-Inclusion---MyAccessibilityBuddy/releases/tag/v5.0.0
[4.0.0]: https://github.com/anthropics/Innovate-For-Inclusion---MyAccessibilityBuddy/releases/tag/v4.0.0
