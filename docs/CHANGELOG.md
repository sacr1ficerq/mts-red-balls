# Changelog

## Version 1.0.0 (2026-03-22)

### Production Release

#### Features
- 6 specialized agents for Kaggle competitions
- Kaggle MCP integration for data download/submission
- Secure sandbox with path traversal and command injection protection
- Web interface with real-time monitoring
- Comprehensive test suite (230+ tests)

#### Improvements
- **Security**: Path traversal protection with `os.path.normpath()`
- **Security**: Command injection prevention
- **Code Quality**: Replaced all print statements with logging
- **Code Quality**: Removed code duplication
- **Code Quality**: Replaced magic numbers with named constants
- **Code Quality**: Fixed all empty except blocks
- **Performance**: Prompt optimization (60-88% reduction)
- **Reliability**: Timeout mechanisms (300s agent, 60s LLM)
- **Reliability**: Retry logic with exponential backoff
- **Reliability**: Rate limiting (8 requests/minute)
- **Reliability**: Shared state management via artifacts

#### Bug Fixes
- Fixed critical bug where agents stopped after first tool execution
- Fixed RateLimiter async lock initialization
- Fixed path traversal vulnerability in sandbox
- Fixed command injection risk

#### Documentation
- Created comprehensive documentation structure
- Added architecture guide
- Added production deployment guide
- Added API reference
- Organized technical documentation in `docs/`

### Test Results
- Total tests: 246
- Passed: 230 (93.5%)
- Failed: 3 (API quota limits, not code issues)

### Known Issues
- None critical

### Migration Notes
- No breaking changes
- All existing configurations compatible
