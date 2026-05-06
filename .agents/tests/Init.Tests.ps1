# Agent OS — init.ps1 Pester Tests
#
# Protects the key init concepts:
#   1. Idempotency — fast exit when .agents/mcp/config.json + .opencode/opencode.json exist
#   2. Global opencode.json clone — copies ~/.config/opencode/opencode.json to project .opencode/
#   3. Plan ID memory binding — sed patches memory-pool URL with ?plan_id=<plan_id>
#   4. Architecture — ostwin run calls init.ps1 with -PlanId (env setup + binding); Start-Plan.ps1 does NOT

BeforeAll {
    $script:InitPs1 = Join-Path (Resolve-Path "$PSScriptRoot/..").Path "init.ps1"
    $script:OstwinBash = Join-Path (Resolve-Path "$PSScriptRoot/../bin").Path "ostwin"
    $script:OstwinPs1 = Join-Path (Resolve-Path "$PSScriptRoot/../bin").Path "ostwin.ps1"
    $script:StartPlanPs1 = Join-Path (Resolve-Path "$PSScriptRoot/../plan").Path "Start-Plan.ps1"
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 1: Idempotency — fast exit when already initialized
# ─────────────────────────────────────────────────────────────────────────────
Describe "init.ps1 — Idempotency" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null
    }

    It "exits early when .agents/mcp/config.json AND .opencode/opencode.json both exist" {
        # Scaffold the files that trigger fast-exit
        $mcpDir = Join-Path $script:projectDir ".agents" "mcp"
        New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
        '{"servers":{}}' | Out-File (Join-Path $mcpDir "config.json") -Encoding utf8

        $opcDir = Join-Path $script:projectDir ".opencode"
        New-Item -ItemType Directory -Path $opcDir -Force | Out-Null
        '{"mcp":{}}' | Out-File (Join-Path $opcDir "opencode.json") -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir 2>&1
        $outputStr = $output -join "`n"
        $outputStr | Should -Match "already initialized"
        # Should NOT show the full banner
        $outputStr | Should -Not -Match "Ostwin -- MCP Configuration"
    }

    It "runs full init when .agents/mcp/config.json is missing" {
        # Only create .opencode — missing mcp/config.json should trigger full init
        $opcDir = Join-Path $script:projectDir ".opencode"
        New-Item -ItemType Directory -Path $opcDir -Force | Out-Null
        '{"mcp":{}}' | Out-File (Join-Path $opcDir "opencode.json") -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir 2>&1
        $outputStr = $output -join "`n"
        # Should show the banner (full init runs)
        $outputStr | Should -Match "Ostwin -- MCP Configuration"
    }

    It "runs full init when .opencode/opencode.json is missing" {
        # Only create mcp/config.json — missing opencode should trigger full init
        $mcpDir = Join-Path $script:projectDir ".agents" "mcp"
        New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
        '{"servers":{}}' | Out-File (Join-Path $mcpDir "config.json") -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir 2>&1
        $outputStr = $output -join "`n"
        $outputStr | Should -Match "Ostwin -- MCP Configuration"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 1b: Idempotency with -PlanId — re-runs when plan_id not yet bound
# ─────────────────────────────────────────────────────────────────────────────
Describe "init.ps1 — Idempotency with -PlanId" {
    BeforeEach {
        $script:projectDir = Join-Path $TestDrive "project-$(Get-Random)"
        New-Item -ItemType Directory -Path $script:projectDir -Force | Out-Null

        # Scaffold a fully initialized project
        $mcpDir = Join-Path $script:projectDir ".agents" "mcp"
        New-Item -ItemType Directory -Path $mcpDir -Force | Out-Null
        '{"servers":{}}' | Out-File (Join-Path $mcpDir "config.json") -Encoding utf8

        $opcDir = Join-Path $script:projectDir ".opencode"
        New-Item -ItemType Directory -Path $opcDir -Force | Out-Null
    }

    It "exits early when plan_id is already bound in the URL" {
        $opcFile = Join-Path $script:projectDir ".opencode" "opencode.json"
        '{"mcp":{"memory":{"url":"http://localhost:3366/api/memory-pool/mcp?plan_id=abc123"}}}' |
            Out-File $opcFile -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir -PlanId "abc123" 2>&1
        $outputStr = $output -join "`n"
        $outputStr | Should -Match "already initialized"
    }

    It "re-runs when plan_id differs from what is bound" {
        $opcFile = Join-Path $script:projectDir ".opencode" "opencode.json"
        '{"mcp":{"memory":{"url":"http://localhost:3366/api/memory-pool/mcp?plan_id=old-plan"}}}' |
            Out-File $opcFile -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir -PlanId "new-plan" 2>&1
        $outputStr = $output -join "`n"
        # Should NOT fast-exit — the plan_id doesn't match
        $outputStr | Should -Not -Match "already initialized"
    }

    It "re-runs when no plan_id is bound yet but -PlanId is given" {
        $opcFile = Join-Path $script:projectDir ".opencode" "opencode.json"
        '{"mcp":{"memory":{"url":"http://localhost:3366/api/memory-pool/mcp"}}}' |
            Out-File $opcFile -Encoding utf8

        $output = & $script:InitPs1 $script:projectDir -PlanId "my-plan" 2>&1
        $outputStr = $output -join "`n"
        $outputStr | Should -Not -Match "already initialized"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 2: Global opencode.json clone to project .opencode/
# ─────────────────────────────────────────────────────────────────────────────
Describe "init.ps1 — Source Code: opencode.json clone step exists" {
    BeforeAll {
        $script:InitContent = Get-Content $script:InitPs1 -Raw
    }

    It "contains clone section that copies GlobalOpencodeFile to ProjectOpencodeFile" {
        $script:InitContent | Should -Match "Clone global opencode.json"
    }

    It "uses Copy-Item from GlobalOpencodeFile to ProjectOpencodeFile" {
        $script:InitContent | Should -Match "Copy-Item.*GlobalOpencodeFile.*ProjectOpencodeFile"
    }

    It "creates .opencode directory if not present" {
        $script:InitContent | Should -Match "ProjectOpencodeDir"
        $script:InitContent | Should -Match "New-Item.*Directory.*ProjectOpencodeDir"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 3: Plan ID binding — sed patches memory URL with ?plan_id=
# ─────────────────────────────────────────────────────────────────────────────
Describe "init.ps1 — Plan ID memory binding" {
    BeforeAll {
        $script:InitContent = Get-Content $script:InitPs1 -Raw
    }

    It "accepts -PlanId parameter" {
        $script:InitContent | Should -Match '\[string\]\$PlanId'
    }

    It "contains sed binding section" {
        $script:InitContent | Should -Match "Bind plan_id to memory MCP URL"
    }

    It "uses two-pass sed: clean then bind" {
        $script:InitContent | Should -Match 'sedClean'
        $script:InitContent | Should -Match 'sedBind'
    }

    It "has PowerShell fallback for sed" {
        $script:InitContent | Should -Match "Fallback.*PowerShell string replacement"
    }

    It "guards binding on PlanId being non-empty" {
        $script:InitContent | Should -Match 'if \(\$PlanId'
    }

    Context "sed correctness (functional)" {
        It "binds plan_id to a clean memory URL" {
            $testFile = Join-Path $TestDrive "sed-test-$(Get-Random).json"
            '{"mcp":{"memory":{"type":"remote","url":"http://localhost:3366/api/memory-pool/mcp","headers":{}}}}' |
                Out-File $testFile -Encoding utf8

            $sedClean = "s|/api/memory-pool/mcp\?plan_id=[^""]*|/api/memory-pool/mcp|g"
            $sedBind  = "s|/api/memory-pool/mcp""|/api/memory-pool/mcp?plan_id=test-plan-123""|g"
            & sed -i '' -e $sedClean -e $sedBind $testFile 2>$null

            $result = Get-Content $testFile -Raw
            $result | Should -Match 'plan_id=test-plan-123'
            # Should still be valid JSON
            $null = $result | ConvertFrom-Json
        }

        It "replaces existing plan_id (idempotent re-bind)" {
            $testFile = Join-Path $TestDrive "sed-rebind-$(Get-Random).json"
            '{"mcp":{"memory":{"url":"http://localhost:3366/api/memory-pool/mcp?plan_id=old-plan"}}}' |
                Out-File $testFile -Encoding utf8

            $sedClean = "s|/api/memory-pool/mcp\?plan_id=[^""]*|/api/memory-pool/mcp|g"
            $sedBind  = "s|/api/memory-pool/mcp""|/api/memory-pool/mcp?plan_id=new-plan""|g"
            & sed -i '' -e $sedClean -e $sedBind $testFile 2>$null

            $result = Get-Content $testFile -Raw
            $result | Should -Match 'plan_id=new-plan'
            $result | Should -Not -Match 'plan_id=old-plan'
        }

        It "does not corrupt other MCP server URLs" {
            $testFile = Join-Path $TestDrive "sed-safety-$(Get-Random).json"
            $content = @'
{
  "mcp": {
    "memory": {"url": "http://localhost:3366/api/memory-pool/mcp"},
    "channel": {"url": "http://localhost:3366/api/channel/mcp"},
    "knowledge": {"command": "python3 -m knowledge_mcp"}
  }
}
'@
            $content | Out-File $testFile -Encoding utf8

            $sedClean = "s|/api/memory-pool/mcp\?plan_id=[^""]*|/api/memory-pool/mcp|g"
            $sedBind  = "s|/api/memory-pool/mcp""|/api/memory-pool/mcp?plan_id=xyz""|g"
            & sed -i '' -e $sedClean -e $sedBind $testFile 2>$null

            $result = Get-Content $testFile -Raw
            $result | Should -Match 'memory-pool/mcp\?plan_id=xyz'
            # Channel URL must NOT be modified
            $result | Should -Match '/api/channel/mcp"'
            $result | Should -Not -Match 'channel.*plan_id'
        }
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 4: Architecture — ostwin run calls init.ps1 for env setup (no -PlanId)
#   Plan_id binding is handled separately by Start-Plan.ps1 via init.ps1 -PlanId
# ─────────────────────────────────────────────────────────────────────────────
Describe "ostwin — Calls init.ps1 in run command for env setup" {
    BeforeAll {
        $script:OstwinContent = Get-Content $script:OstwinPs1 -Raw
    }

    It "run command calls init.ps1 for project initialization" {
        $runSection = [regex]::Match(
            $script:OstwinContent,
            '(?s)"run"\s*\{.*?# Dispatch to Start-Plan'
        ).Value
        if ($runSection) {
            $runSection | Should -Match 'init\.ps1' `
                -Because "ostwin run must call init.ps1 to ensure .agents/ and .opencode/ exist"
        }
    }

    It "run command passes -PlanId derived from plan filename to init.ps1" {
        $runSection = [regex]::Match(
            $script:OstwinContent,
            '(?s)"run"\s*\{.*?# Dispatch to Start-Plan'
        ).Value
        if ($runSection) {
            $runSection | Should -Match 'initPlanId' `
                -Because "ostwin run must extract plan_id from the plan filename"
            $runSection | Should -Match '-PlanId.*initPlanId' `
                -Because "ostwin run must pass -PlanId to init.ps1 for memory URL binding"
        }
    }

    It "falls back to Get-Location when resolvedWorkingDir is empty" {
        # Prevents the bug where empty $resolvedWorkingDir passes nothing to init.ps1,
        # causing it to default to "." (ostwin process CWD instead of project dir)
        $runSection = [regex]::Match(
            $script:OstwinContent,
            '(?s)"run"\s*\{.*?# Dispatch to Start-Plan'
        ).Value
        if ($runSection) {
            $runSection | Should -Match 'Get-Location' `
                -Because "init.ps1 must receive a resolved path even when working_dir is unset"
        }
    }

    It "passes initTarget (not raw resolvedWorkingDir) to init.ps1" {
        $runSection = [regex]::Match(
            $script:OstwinContent,
            '(?s)"run"\s*\{.*?# Dispatch to Start-Plan'
        ).Value
        if ($runSection) {
            $runSection | Should -Match 'init\.ps1 \$initTarget' `
                -Because "init.ps1 must receive the resolved initTarget, not the potentially-empty resolvedWorkingDir"
        }
    }

    It "still handles 'init' as a standalone subcommand" {
        $script:OstwinContent | Should -Match '"init"' `
            -Because "ostwin init must remain as a user-facing command"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 5: Start-Plan.ps1 does NOT handle init or plan_id binding
#   All init logic (env setup + plan_id binding) is handled by ostwin → init.ps1
# ─────────────────────────────────────────────────────────────────────────────
Describe "Start-Plan.ps1 — Does NOT handle init or plan_id binding" {
    BeforeAll {
        $script:StartPlanContent = Get-Content $script:StartPlanPs1 -Raw
    }

    It "does NOT call init.ps1" {
        $script:StartPlanContent | Should -Not -Match '& \$initPs1.*-PlanId' `
            -Because "init.ps1 is called by ostwin, not Start-Plan.ps1"
    }

    It "does NOT contain inline sed binding logic" {
        $script:StartPlanContent | Should -Not -Match 'sedClean.*sedBind' `
            -Because "sed binding logic must be centralized in init.ps1, not duplicated"
    }

    It "does NOT directly modify opencode.json" {
        $script:StartPlanContent | Should -Not -Match 'Out-File.*opencode\.json' `
            -Because "opencode.json modifications belong in init.ps1"
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# CONCEPT 6: init.ps1 parameter contract
# ─────────────────────────────────────────────────────────────────────────────
Describe "init.ps1 — Parameter contract" {
    BeforeAll {
        $script:InitContent = Get-Content $script:InitPs1 -Raw
    }

    It "accepts TargetDir as Position 0" {
        $script:InitContent | Should -Match '\[Parameter\(Position = 0\)\]'
        $script:InitContent | Should -Match '\[string\]\$TargetDir'
    }

    It "accepts optional PlanId parameter" {
        $script:InitContent | Should -Match '\[string\]\$PlanId'
    }

    It "accepts -Yes switch for non-interactive mode" {
        $script:InitContent | Should -Match "\[switch\]\`$Yes"
    }

    It "accepts -Help switch" {
        $script:InitContent | Should -Match "\[switch\]\`$Help"
    }

    It "defaults TargetDir to current directory" {
        $script:InitContent | Should -Match '\$TargetDir\s*=\s*"\."'
    }

    It "defaults PlanId to empty string" {
        $script:InitContent | Should -Match '\$PlanId\s*=\s*""'
    }
}
