# Plan: Example Feature

## Config
working_dir: /path/to/your/project

## Epic: EPIC-001 — Build core module

Create the core module with foundational functionality:
- Set up the module structure and public API
- Implement primary business logic
- Include inline documentation

The engineer will decompose this into sub-tasks and create TASKS.md.

Acceptance criteria:
- Module is importable and functional
- Core API methods work as documented
- All tests pass

## Epic: EPIC-002 — Add test coverage and CLI

Build comprehensive tests and a command-line interface:
- Unit tests for all core module functions
- Integration tests for end-to-end workflows
- CLI with argument parsing and help text

Acceptance criteria:
- Test suite passes with full coverage of core module
- CLI supports required commands and flags
- `--help` shows usage information

## Epic: EPIC-003 — Documentation and packaging

Prepare the project for distribution:
- README with usage examples
- API documentation
- Package configuration (setup.py / pyproject.toml)

Acceptance criteria:
- README covers installation, usage, and examples
- Package installs cleanly via pip
