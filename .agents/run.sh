#!/bin/bash
pwsh -NoProfile -Command "Invoke-Pester -Path /Users/paulaan/PycharmProjects/agent-os/.agents/plan/Start-Plan.Tests.ps1 -Output Detailed" > /tmp/pester_final.txt 2>&1

