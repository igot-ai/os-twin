---
name: sdk-design
description: Design internal SDKs and libraries with clean APIs, semantic versioning, comprehensive documentation, migration guides, and backward compatibility strategies. Produces SDK design documents that balance usability with flexibility.
---

# sdk-design

## Purpose

Internal SDKs are the interface between platform and product. A well-designed SDK makes feature teams productive; a poorly designed one becomes a bottleneck they work around.

## SDK Design Principles

1. **Pit of success** — make the correct usage the easiest usage
2. **Minimal surface** — expose only what's necessary; internals are private
3. **Consistent** — same patterns across all SDK methods
4. **Documented** — every public method has documentation and examples
5. **Versioned** — semver, with clear upgrade paths

## SDK Design Document Template

```markdown
# SDK Design: [Library Name]

**Version:** [semver]
**Author:** platform-engineer
**Status:** Draft | In Review | Released

## Purpose
[What problem this SDK solves and for whom]

## Target Users
[Which teams/roles will use this SDK]

## API Surface

### Core API
| Method | Parameters | Returns | Description |
|--------|-----------|---------|-------------|
| `create(config)` | `Config` | `Resource` | Creates a new resource |
| `get(id)` | `string` | `Resource | null` | Retrieves by ID |

### Configuration
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `timeout` | `number` | `5000` | Request timeout in ms |
| `retries` | `number` | `3` | Max retry attempts |

## Error Handling
[How errors are surfaced — exceptions, result types, error codes]

## Versioning Strategy
- Major: breaking API changes (with migration guide)
- Minor: new features, backward compatible
- Patch: bug fixes

## Usage Examples
[At least 3 real-world examples]

## Migration Guide (from vX to vY)
[Step-by-step upgrade instructions]
```

## Anti-Patterns

- Designing the API in isolation → talk to consumers before finalizing
- Too many configuration options → sensible defaults cover 80% of use cases
- Leaking implementation details → consumers shouldn't need to know how it works internally
- No deprecation strategy → old APIs should be deprecated gracefully, not removed abruptly
