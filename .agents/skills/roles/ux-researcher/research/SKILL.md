---
name: research
description: Conduct market, technical, or domain research
tags: [researcher, research, analysis]
: core
source: project
---

# Workflow: Research

**Goal:** Conduct structured market, technical, or domain research — producing an actionable report with findings, competitive analysis, and specific recommendations for the game project.

**Input:** Research topic + context from project
**Output:** `.output/research/{topic}.md` — report with executive summary and recommendations

---

## Step 1 — Define Research Scope

Ask:
1. "What is the research topic?"
2. "What specific question must the research answer?"
3. "How will the findings be used? (GDD decision / architecture choice / monetization model)"
4. "Any specific competitors, technologies, or domains to focus on?"
5. "Depth: quick scan (30min) or thorough analysis (2-3h)?"

---

## Step 2 — Gather Information

**Market / Competitor Research:**
- Identify 3-5 comparable products/games
- For each: core mechanics, monetization, ratings, player reviews, unique differentiators
- Look for patterns across the competitive set

**Technology Evaluation:**
- Compare options on: performance, maturity, license, Unity compatibility, community support
- Score each option on weighted criteria (must define weights upfront)

**Domain / Design Research:**
- Define key concepts and vocabulary
- Identify industry standards and best practices
- Find relevant case studies or post-mortems

---

## Step 3 — Write Research Report

```markdown
# Research: {Topic}

**Date:** {date}
**Question:** {specific question being answered}
**Used for:** {how findings will be applied}

## Executive Summary

{2-3 sentences: key finding + recommended action}

## Findings

### {Subtopic 1}
{findings with evidence}

### Competitive Analysis (if applicable)

| Product | {Criteria 1} | {Criteria 2} | {Criteria 3} | Score |
|---------|------------|------------|------------|-------|
| {name} | {rating} | {rating} | {rating} | {N}/10 |

### {Subtopic 2}
{findings}

## Gaps and Risks

{What's unknown / what could invalidate these findings}

## Recommendations

1. **{Action}** — {rationale}
   → Affects: {GDD section / architecture decision / roadmap item}
2. ...

## Sources

{List of sources, articles, or references consulted}
```

---

## Step 4 — Save

1. Create `.output/research/` if needed.
2. Save to `.output/research/{topic-kebab-case}.md`.
3. Report: "Research complete. Key finding: {summary}. Top recommendation: {recommendation}."
4. Suggest: "Apply finding to GDD: `[game-designer] update gdd`" or appropriate next step.
