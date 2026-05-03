---
name: build-verify
description: Use this skill to install project dependencies and build the application — detect the project type, run the correct install and build commands, and report any failures.
tags: [qa, build, dependencies, install, verification]

---

# build-verify

## Overview

This skill guides QA (or any agent) through the full **dependency install + build** cycle for a project. It detects the project type from lock files and config files, runs the correct package-manager and build commands, and reports structured results — pass or fail with error output.

Use this as the **first step** before running tests or reviewing code, so you can verify the project compiles cleanly from a fresh state.

## When to Use

- Before running the test suite during a review (deps must be installed first)
- When a `review` or `task` message arrives and the project has not been built yet
- When the engineer's done message mentions adding new dependencies
- When you encounter `MODULE_NOT_FOUND`, `ImportError`, build errors, or missing-binary errors
- When re-reviewing after a fix that changed `package.json`, `requirements.txt`, `Cargo.toml`, or any dependency file

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Build log | Terminal output | Displayed inline |
| Build verdict | Structured text | Included in QA report |

## Instructions

### 1. Detect the Project Type

From the project's **working directory** (check `config.json` → `assignment.working_dir`, or fall back to the repository root), look for these marker files to identify the ecosystem.

Probe in this priority order — stop at the **first match**:

| Marker File | Ecosystem | Package Manager |
|-------------|-----------|-----------------|
| `bun.lockb` or `bun.lock` | Node.js | bun |
| `pnpm-lock.yaml` | Node.js | pnpm |
| `yarn.lock` | Node.js | yarn |
| `package-lock.json` | Node.js | npm |
| `package.json` (no lockfile) | Node.js | npm (fallback) |
| `requirements.txt` or `pyproject.toml` or `setup.py` | Python | pip / uv |
| `Cargo.toml` | Rust | cargo |
| `go.mod` | Go | go |
| `Gemfile` | Ruby | bundler |
| `composer.json` | PHP | composer |
| `*.csproj` or `*.sln` | .NET | dotnet |
| `Makefile` | Generic | make |

If **none** of these exist, skip to step 4 and note "no build system detected".

### 2. Install Dependencies

Run the install command for the detected ecosystem. Always prefer the **lockfile-aware** variant so builds are reproducible.

```
Ecosystem   | Command
------------|----------------------------------------
bun         | bun install --frozen-lockfile
pnpm        | pnpm install --frozen-lockfile
yarn        | yarn install --frozen-lockfile
npm         | npm ci                (if package-lock.json exists)
            | npm install           (otherwise)
pip         | pip install -r requirements.txt
uv          | uv sync               (if pyproject.toml has [tool.uv])
poetry      | poetry install --no-interaction
cargo       | (no separate install step — cargo build fetches deps)
go          | go mod download
bundler     | bundle install
composer    | composer install --no-interaction
dotnet      | dotnet restore
make        | (no separate install step)
```

**On failure:**
- Capture the full error output.
- Check for common issues:
  - Wrong runtime version (e.g., Node 16 vs 20) — look for `.nvmrc`, `.node-version`, `.python-version`, `.tool-versions`.
  - Missing system-level dependencies (e.g., `libssl-dev`, `pkg-config`).
  - Network errors (registry unreachable).
- Report the failure and stop — do NOT proceed to the build step.

### 3. Build the Application

Run the build command for the detected ecosystem:

```
Ecosystem   | Command
------------|----------------------------------------
bun         | bun run build          (if "build" script in package.json)
pnpm        | pnpm run build
yarn        | yarn build
npm         | npm run build
pip/uv      | python -m build  OR  pip install -e .  (if setup.py/pyproject.toml)
cargo       | cargo build
go          | go build ./...
dotnet      | dotnet build
make        | make
```

**Skip the build step** if:
- There is no `build` script in `package.json` (for Node.js projects).
- The project is a pure library with no compilation step.
- The ecosystem doesn't have a separate build step (e.g., raw Python scripts).

To check if a Node.js project has a build script:
```bash
node -e "const p=require('./package.json'); process.exit(p.scripts?.build ? 0 : 1)" 2>/dev/null
```

**On failure:**
- Capture the full error output (first 100 lines + last 20 lines if very long).
- Identify the root error — look for the **first** `error`, `Error:`, `FAILED`, or non-zero exit.
- Report the failure with the error context.

### 4. Verify the Build

After install + build succeed, verify:

- [ ] Exit code was 0 for both install and build commands
- [ ] No error-level warnings in the output (e.g., `npm ERR!`, `warning: unused`, `DeprecationWarning` at error level)
- [ ] Expected output artifacts exist (e.g., `dist/`, `build/`, `target/`, `.next/`)

### 5. Report the Result

Include a build section in your QA report or channel message:

**On success:**
```
## Build Verification
- Ecosystem: <detected ecosystem>
- Install: `<command>` — OK
- Build: `<command>` — OK (or SKIPPED if no build step)
- Artifacts: <dist/, build/, etc.>
```

**On failure:**
```
## Build Verification — FAILED
- Ecosystem: <detected ecosystem>
- Step failed: install | build
- Command: `<command that failed>`
- Exit code: <N>
- Error:
  <first relevant error lines>
- Suggested fix: <hint based on error analysis>
```

## Verification

After completing this skill:
1. The install command ran to completion (exit 0) or failure is clearly reported
2. The build command ran to completion (exit 0) or was correctly skipped
3. The result is captured in a structured format for inclusion in the QA report
4. No silent failures — every non-zero exit code is reported
