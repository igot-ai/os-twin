#!/bin/bash
export AGENT_OS_ROOM_DIR='/Users/paulaan/PycharmProjects/agent-os/.agents/roles/reporter/data/.war-rooms/room-000'
export AGENT_OS_ROLE='architect'
export AGENT_OS_PARENT_PID='92272'
export AGENT_OS_SKILLS_DIR='/Users/paulaan/PycharmProjects/agent-os/.agents/roles/reporter/data/.war-rooms/room-000/artifacts/skills'

'/Users/paulaan/PycharmProjects/agent-os/.agents/bin/agent' -n "$(cat '/Users/paulaan/PycharmProjects/agent-os/.agents/roles/reporter/data/.war-rooms/room-000/artifacts/prompt.txt')" --agent architect --auto-approve --model gemini-3.1-pro-preview --quiet > '/Users/paulaan/PycharmProjects/agent-os/.agents/roles/reporter/data/.war-rooms/room-000/artifacts/architect-output.txt' 2>&1