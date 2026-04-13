Analysis Summary
Current install.sh problems:
- 1926 lines monolithic -- single file mixing 12+ concerns
- Embedded Python heredocs -- 4 inline Python scripts for JSON patching (~200 lines)
- Duplicated code -- build_nextjs() and build_dashboard_fe() are near-identical (~90% overlap)
- Hard-coded versions scattered (Node v25.8.1, PowerShell 7.4.7, Python 3.12)
- No testability -- zero unit tests for the installer itself
- No Windows path -- ostwin CLI (1291 lines bash) + 13 shell scripts = full blockers
- Mixed lifecycle -- install, build, config, start, verify all in one pass
What already works cross-platform:
- 50+ PowerShell scripts (plan engine, roles, channels, war-rooms)
- 6 Windows desktop automation scripts in .agents/scripts/windows/
- All Python code (dashboard, MCP, memory)
- All Node.js/TypeScript code
---
Here is the plan:
---
## EPIC-001 -- Modularize install.sh into Composable Shell Modules
Roles: engineer, qa
Goal: Decompose the monolithic 1926-line install.sh into discrete, testable modules organized by concern, creating a shared library layer and eliminating code duplication -- without changing any external behavior.
Definition of Done
- [ ] install.sh is a thin orchestrator (<150 lines) that sources modules from .agents/installer/
- [ ] Each module is a standalone file with a single responsibility (OS detect, dependency check, dependency install, venv setup, env setup, file sync, MCP patch, dashboard build, dashboard start, channel setup, PATH setup, verification)
- [ ] Embedded Python heredocs are extracted into standalone .py files under .agents/installer/scripts/
- [ ] build_nextjs() and build_dashboard_fe() are unified into a single build_frontend() function
- [ ] Hard-coded versions are centralized in a single versions.conf file
- [ ] A shared lib.sh provides: header(), ok(), warn(), fail(), info(), step(), ask(), version_gte(), detect_os()
- [ ] All existing CLI flags (--yes, --dir, --dashboard-only, --channel, --source-dir, --port, --skip-optional) continue to work identically
- [ ] install.sh --help output is unchanged
Acceptance Criteria
- [ ] Running ./install.sh --yes on a clean macOS machine produces identical results to the current monolith => depends_on: []
- [ ] Running ./install.sh --yes on a clean Ubuntu machine produces identical results => depends_on: []
- [ ] Running ./install.sh --dashboard-only works identically => depends_on: []
- [ ] Each module in .agents/installer/ can be sourced independently without side effects => depends_on: []
- [ ] shellcheck passes on all modules with zero errors => depends_on: []
- [ ] At least 1 BATS test per module validates its core function => depends_on: []
Proposed Module Structure
.agents/installer/
  lib.sh              # Colors, formatting, ask(), version_gte()
  versions.conf       # MIN_PYTHON=3.10, NODE_VER=v25.8.1, PWSH_VER=7.4.7, etc.
  detect-os.sh        # detect_os(), ARCH, DISTRO, PKG_MGR
  check-deps.sh       # check_python(), check_pwsh(), check_node(), check_uv(), check_opencode()
  install-deps.sh     # install_brew(), install_uv(), install_python(), install_pwsh(), install_node(), install_opencode()
  install-files.sh    # install_files(), rsync/cp logic, MCP seeding, symlinks, migrations
  setup-venv.sh       # setup_venv(), pip/uv dependency sync
  setup-env.sh        # setup_env(), .env creation, API key prompting, .env.sh hook
  patch-mcp.sh        # patch_mcp_config(), env injection, OpenCode merge
  build-frontend.sh   # Unified build_frontend(dir, label) for nextjs + fe
  setup-path.sh       # setup_path(), shell RC detection
  setup-opencode.sh   # setup_opencode_permissions()
  sync-agents.sh      # sync_opencode_agents()
  start-dashboard.sh  # Dashboard launch, health check, tunnel detection
  start-channels.sh   # Channel connector install + launch
  verify.sh           # Component status display
  scripts/
    patch_opencode_permissions.py
    inject_env_to_mcp.py
    merge_mcp_builtin.py
    merge_mcp_to_opencode.py
---
## EPIC-002 -- Windows Standalone Installer (`install.ps1`)
**Roles:** engineer, qa, architect
**Goal:** Create a PowerShell-based installer for Windows that provides feature parity with the modularized bash installer, enabling full Agent OS operation on Windows 10/11 without WSL.
### Definition of Done
- [ ] `install.ps1` exists at `.agents/install.ps1` and mirrors every step of `install.sh`
- [ ] Windows-specific OS detection: architecture, Windows version, package manager (winget/choco/scoop)
- [ ] Dependency installation via winget (preferred), chocolatey, or direct download for: Python 3.10+, PowerShell 7+, uv, Node.js, opencode
- [ ] Python venv creation and dependency sync works on Windows (`.venv\Scripts\python.exe`)
- [ ] `.env` file creation with Windows-compatible `sed` replacement (PowerShell `-replace`)
- [ ] MCP config patching reuses the extracted `.py` scripts from EPIC-001
- [ ] File installation uses `Copy-Item -Recurse` or `robocopy` (no rsync dependency)
- [ ] PATH setup writes to `$PROFILE` (PowerShell) and/or User `PATH` environment variable
- [ ] Dashboard starts via `Start-Process -NoNewWindow` with PID tracking
- [ ] Symlink creation uses `New-Item -ItemType SymbolicLink` with Developer Mode detection
- [ ] `install.ps1 -Help`, `-Yes`, `-Dir`, `-DashboardOnly`, `-Channel`, `-Port`, `-SourceDir` flags mirror bash equivalents
- [ ] No dependency on WSL, Cygwin, or Git Bash
### Acceptance Criteria
- [ ] Running `.\install.ps1 -Yes` on a clean Windows 11 machine installs all components => depends_on: [EPIC-001]
- [ ] Running `.\install.ps1 -DashboardOnly` installs dashboard-only subset => depends_on: [EPIC-001]
- [ ] `ostwin health` succeeds after installation on Windows => depends_on: [EPIC-003]
- [ ] All MCP servers start and respond to health checks on Windows => depends_on: [EPIC-001]
- [ ] Pester test suite passes on Windows after installation => depends_on: []
- [ ] Dashboard UI is accessible at `http://localhost:9000` on Windows => depends_on: []
---
##EPIC-003 -- Windows ostwin CLI (ostwin.ps1)
Roles: engineer, qa
Goal: Port the 1291-line bash ostwin CLI to PowerShell, providing full command parity on Windows, with a thin ostwin.cmd wrapper for native CMD/terminal invocation.
Definition of Done
- [ ] ostwin.ps1 exists at .agents/bin/ostwin.ps1 with all 25+ subcommands ported
- [ ] ostwin.cmd wrapper exists for cmd.exe / Windows Terminal invocation
- [ ] ps_dispatch() pattern is replaced with native PowerShell script invocation (no dual-dispatch needed)
- [ ] .env loading works with Windows path separators and $env: variables
- [ ] Process management uses Start-Process/Stop-Process/Get-Process instead of nohup/kill/lsof
- [ ] PID files use Windows-compatible paths ($env:USERPROFILE\.ostwin\dashboard.pid)
- [ ] Dashboard health checks use Invoke-RestMethod instead of curl
- [ ] Plan resolution, role cloning, skill management all function on Windows
Acceptance Criteria
- [ ] Every ostwin <command> that works on macOS/Linux also works on Windows via ostwin.ps1 => depends_on: EPIC-002
- [ ] ostwin run executes plans successfully on Windows => depends_on: EPIC-002
- [ ] ostwin plan create/start/list/clear work against dashboard API => depends_on: EPIC-002
- [ ] ostwin skills install/search/list work on Windows => depends_on: EPIC-002
- [ ] ostwin stop gracefully terminates dashboard and channel processes => depends_on: EPIC-002
- [ ] ostwin agent <role> launches agents via opencode on Windows => depends_on: EPIC-002
---
## EPIC-004 -- Port Supporting Shell Scripts to PowerShell
Roles: engineer, qa
Goal: Port the 13 remaining bash lifecycle scripts to PowerShell equivalents so every ostwin subcommand has a Windows-native backend.
Definition of Done
- [ ] Each script below has a .ps1 equivalent in the same directory:
Bash Script	PowerShell Port	Lines
init.sh	init.ps1	~226
dashboard.sh	dashboard.ps1	~110
stop.sh	stop.ps1	~95
health.sh	health.ps1	~166
sync.sh	sync.ps1	~132
sync-skills.sh	sync-skills.ps1	~332
logs.sh	logs.ps1	~147
config.sh	config.ps1	~95
uninstall.sh	uninstall.ps1	~89
memory-monitor.sh	memory-monitor.ps1	~92
clawhub-install.sh	clawhub-install.ps1	~557
bin/agent	bin/agent.ps1	~55
bin/memory	bin/memory.ps1	~229
- [ ] The ostwin.ps1 CLI (EPIC-003) dispatches to .ps1 versions when running on Windows
- [ ] Existing .sh scripts remain untouched (no regressions on macOS/Linux)
Acceptance Criteria
- [ ] ostwin init ~/my-project works on Windows => depends_on: EPIC-003
- [ ] ostwin dashboard, ostwin stop, ostwin health, ostwin logs all function on Windows => depends_on: EPIC-003
- [ ] ostwin sync updates framework files correctly on Windows (NTFS paths) => depends_on: EPIC-003
- [ ] ostwin skills install <url> fetches and installs skills on Windows => depends_on: EPIC-003
- [ ] ostwin config reads/writes settings correctly on Windows => depends_on: EPIC-003
- [ ] At least 1 Pester test per ported script validates core behavior => depends_on: []
---
## EPIC-005 -- Cross-Platform CI/CD and Test Harness
Roles: engineer, qa, architect
Goal: Extend the existing GitHub Actions CI to validate both the modularized bash installer and the new Windows installer, ensuring no regressions on any platform.
Definition of Done
- [ ] GitHub Actions matrix strategy runs on: ubuntu-latest, macos-latest, windows-latest
- [ ] BATS test suite for .agents/installer/*.sh modules runs on macOS + Linux
- [ ] Pester test suite for .agents/installer/*.ps1 runs on Windows
- [ ] Existing Pester tests (50+ files) pass on all three platforms
- [ ] Smoke test: install.sh --yes --skip-optional completes on Linux CI
- [ ] Smoke test: install.ps1 -Yes -SkipOptional completes on Windows CI
- [ ] Dashboard health check passes post-install on all platforms
- [ ] Test results published as GitHub Actions artifacts with JUnit XML
Acceptance Criteria
- [ ] CI green on all 3 platforms for every PR touching .agents/ => depends_on: EPIC-001, EPIC-002
- [ ] BATS tests cover at least 80% of installer module functions => depends_on: EPIC-001
- [ ] Pester tests cover at least 80% of PowerShell installer functions => depends_on: EPIC-002
- [ ] CI run completes in <15 minutes per platform => depends_on: []
- [ ] Failing CI blocks merge to main => depends_on: []
---
Dependency Graph
EPIC-001 (Modularize install.sh)
   │
   ├──> EPIC-002 (Windows install.ps1)
   │       │
   │       ├──> EPIC-003 (Windows ostwin.ps1 CLI)
   │       │       │
   │       │       └──> EPIC-004 (Port 13 shell scripts)
   │       │
   │       └──> EPIC-005 (Cross-platform CI)
   │
   └──> EPIC-005 (Cross-platform CI)
Estimated scope: ~4,500 lines of new PowerShell code, ~500 lines of BATS tests, 300 lines of CI config, and refactoring 1,926 lines of existing bash into ~1,200 lines across 17 modules.