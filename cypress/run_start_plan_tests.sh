#!/bin/bash
pwsh -NoProfile -Command "Invoke-Pester -Path /Users/paulaan/PycharmProjects/agent-os/.agents/plan/Expand-Plan.Tests.ps1 -Output Detailed"
