#!/bin/bash
export AGENT_OS_ROOM_DIR='/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001'
export AGENT_OS_ROLE='game-engineer'
export AGENT_OS_PARENT_PID='68846'
export AGENT_OS_SKILLS_DIR='/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/skills'
export AGENT_OS_PID_FILE='/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/pids/game-engineer.pid'
export OSTWIN_HOME='/Users/paulaan/.ostwin'
export AGENT_OS_PROJECT_DIR='/Users/paulaan/Downloads/snakie/snakie_project'

# Write PID before exec — $$ survives exec, so this is the real agent PID.
# bin/agent also writes this (harmless overwrite); this fallback ensures
# non-bin/agent commands (deepagents, custom CLIs) still get tracked.
echo "$$" > '/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/pids/game-engineer.pid'
# Log diagnostic info before exec
echo "[wrapper] PID=$$, CMD='/Users/paulaan/.ostwin/bin/agent', CWD=$(pwd)" >> '/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/artifacts/game-engineer-output.txt'
exec '/Users/paulaan/.ostwin/bin/agent' -n "$(cat '/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/artifacts/prompt.txt')" --agent game-engineer --auto-approve --model google-vertex/gemini-3.1-pro-preview --quiet --mcp-config /Users/paulaan/Downloads/snakie/snakie_project/.agents/mcp/mcp-config.json >> '/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/artifacts/game-engineer-output.txt' 2>&1
# If exec fails, this line runs:
echo "[wrapper] EXEC FAILED: exit=$?" >> '/Users/paulaan/Downloads/snakie/snakie_project/.war-rooms/room-001/artifacts/game-engineer-output.txt'