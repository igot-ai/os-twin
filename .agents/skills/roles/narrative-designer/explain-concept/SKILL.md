---
name: explain-concept
description: Explain a technical concept clearly
tags: [tech-writer, documentation, explanation]

source: project
---

# Workflow: Explain Concept

**Goal:** Create a clear, accessible explanation of a technical concept using analogies, diagrams, and examples calibrated to the stated audience.

**Input:** Concept name + audience level
**Output:** Inline explanation (delivered in conversation)

---

## Step 1 — Define the Explanation

Ask (if not already stated):
1. "What concept needs explanation?"
2. "Who is the audience? (junior dev / designer / senior engineer / non-technical stakeholder)"
3. "What level of detail? (quick overview / deep dive / just the key idea)"
4. "Any specific context — how does this apply to our project?"

---

## Step 2 — Structure the Explanation

Use the "Explain Like Teaching a Friend" structure:

1. **Hook** — Start with a relatable analogy: "It's like {familiar thing}"
2. **Core concept** — One sentence: the essence of what it is
3. **How it works** — 3-5 plain-language bullet points
4. **Diagram** — Mermaid diagram if the concept has structure or flow
5. **Code example** — Minimal, runnable snippet (if technical audience)
6. **Project application** — How this specifically applies to our Unity project
7. **Common mistakes** — What people get wrong about this

---

## Step 3 — Calibrate to Audience

| Audience | Approach |
|----------|---------|
| Non-technical | Analogies only — no code. Focus on outcomes, not implementation |
| Designer | What it enables, not how it works internally |
| Junior dev | Step-by-step, explicit examples, links to Unity docs |
| Senior dev | Direct + technical. Trade-offs, edge cases, performance implications |

---

## Step 4 — Deliver Inline

Present the explanation in the conversation.
Ask: "Does this explanation make sense? Want me to go deeper on any part?"

If the user wants more: zoom into the most relevant section without repeating what was already clear.
