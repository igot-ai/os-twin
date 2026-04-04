# ADR 007: Dashboard v2 Overhaul

**Date:** 2026-04-02
**Status:** Accepted
**Context:** The previous Dashboard layout (v1) was rigidly divided into three static panels (Plan Launcher, War-Rooms, Channel Feed). This UI did not accommodate natural, prompt-driven user workflows, leading to friction when users simply wanted to "ask the agent to build something."
**Decision:** We are migrating to a "prompt-centric" v2 Dashboard architecture.
1. **Unified Chat Flow:** The primary interface will revolve around a `CommandPrompt` that transitions the user into a conversational (`/c/[id]`) flow.
2. **Dynamic Plans via Natural Language:** Users can instruct the agent to generate plans via prompt rather than manually drafting Markdown.
3. **Sidebar Navigation:** A collapsible sidebar replaces the multi-panel layout, providing categorized history (Plans, Conversations) and configuration tabs (MCP, Channels, Settings).
4. **Theming Architecture:** Replaced hardcoded hex strings with a strict `var(--color-*)` CSS variable token system to ensure comprehensive Light/Dark mode switching and glassmorphism.
**Consequences:** 
- Required the creation of a new `ConversationStore` backend to persist chat sessions.
- Required updating End-to-End Cypress tests from checking a static layout to interacting with a dynamic conversational UI.
- Improves user onboarding through interactive "Example Chips" and guided Plan templates.
