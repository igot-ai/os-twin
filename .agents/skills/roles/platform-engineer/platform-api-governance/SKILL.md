---
name: platform-api-governance
description: Define and enforce platform API standards including naming conventions, versioning policies, error formats, deprecation lifecycles, and breaking change protocols. Ensures consistent, predictable APIs across all platform services.
---

# platform-api-governance

## Purpose

Without API governance, every service invents its own conventions. This creates integration friction, documentation inconsistency, and breaking changes without warning. API governance makes platform APIs predictable and reliable.

## API Standards

### Naming Conventions
- Resources are plural nouns: `/users`, `/projects`, `/environments`
- Actions use HTTP verbs: GET (read), POST (create), PUT (replace), PATCH (update), DELETE (remove)
- Nested resources: `/projects/{id}/environments`
- Query parameters for filtering: `?status=active&limit=10`

### Versioning Policy
- Version in URL path: `/api/v1/users`
- Major versions for breaking changes
- Support N-1 version for 6 months minimum
- Deprecation notice 3 months before removal

### Error Response Format
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "User with ID 123 was not found",
    "details": [
      {
        "field": "userId",
        "reason": "not_found"
      }
    ],
    "requestId": "req-abc123"
  }
}
```

### Pagination
```json
{
  "data": [...],
  "pagination": {
    "total": 100,
    "limit": 20,
    "offset": 0,
    "next": "/api/v1/users?offset=20&limit=20"
  }
}
```

## Deprecation Lifecycle

| Phase | Duration | Action |
|-------|----------|--------|
| Announcement | T-3 months | Deprecation notice in docs, `Sunset` header |
| Migration | T-3 to T-1 month | Migration guide published, support for consumers |
| Warning | T-1 month | Log warnings for deprecated usage |
| Removal | T+0 | Remove deprecated API, 404 for old endpoints |

## Breaking Change Protocol

Before making any breaking change:

1. **Identify impact** — which consumers use this API?
2. **Design migration** — how do consumers move to the new API?
3. **Communicate** — notify all consumers with timeline
4. **Support** — provide migration assistance
5. **Verify** — confirm all consumers have migrated before removal

## API Review Checklist

- [ ] Follows naming conventions
- [ ] Uses standard error format
- [ ] Pagination for list endpoints
- [ ] Authentication/authorization documented
- [ ] Rate limits defined
- [ ] OpenAPI/Swagger spec is current
- [ ] No breaking changes without versioning
- [ ] Deprecation timeline follows policy

## Anti-Patterns

- Breaking changes without notice → instant consumer trust destruction
- Inconsistent error formats → every consumer writes different error handling
- No API versioning → can never evolve the API safely
- Standards that exist but aren't enforced → linting and CI checks enforce standards
- Too rigid → standards should enable, not prevent; allow documented exceptions
