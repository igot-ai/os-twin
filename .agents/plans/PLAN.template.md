# Plan: Example Feature

## Config
working_dir: /path/to/your/project

## Task: TASK-001 — Create hello world module

Create a simple Python module at `hello.py` that:
- Defines a function `greet(name)` that returns "Hello, {name}!"
- Includes a `__main__` block that greets "World"

Acceptance criteria:
- `python hello.py` prints "Hello, World!"
- `greet("Agent OS")` returns "Hello, Agent OS!"

## Task: TASK-002 — Add unit tests

Create `test_hello.py` with tests for the hello module:
- Test `greet()` with various names
- Test edge cases (empty string, special characters)
- Tests should pass with `pytest`

Acceptance criteria:
- All tests pass with `pytest test_hello.py`
- At least 3 test cases

## Task: TASK-003 — Add CLI argument support

Update `hello.py` to accept a name via command-line argument:
- Use `argparse` for CLI parsing
- `python hello.py --name "Claude"` prints "Hello, Claude!"
- Default to "World" if no name provided

Acceptance criteria:
- `python hello.py` prints "Hello, World!"
- `python hello.py --name "Test"` prints "Hello, Test!"
- `python hello.py --help` shows usage information
