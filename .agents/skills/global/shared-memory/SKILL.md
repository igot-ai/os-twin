---
name: shared-memory
description: "Use this skill to publish and query cross-room shared memory -- code snippets, file paths, API contracts, and architectural decisions that other agents need to build against."
tags: [global, memory, context, coordination, cross-room]
trust_level: core
---

# shared-memory

## Overview

Shared memory lets agents in different war-rooms share **code-level context** -- file paths, function signatures, API response shapes, model definitions, and import statements. Before you start coding, query memory. After you build something, publish what other rooms need to use it.

The `memory` command is available in your shell. Your room and role are auto-detected.

## What to Publish (and How)

### `code` -- Files, imports, and snippets other agents should use

This is the **most important kind**. Publish every file, function, or class that another room might need to import or call.

```bash
memory publish code "src/models/cat.py -- Cat SQLAlchemy model" \
  --tags models,cat,database,sqlalchemy --ref EPIC-001 \
  --detail "from sqlalchemy import Column, String, Float, Enum
from src.database import Base

class Cat(Base):
    __tablename__ = 'cats'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    breed = Column(String, index=True)
    age = Column(Integer)
    price = Column(Float, nullable=False)
    status = Column(Enum('available','reserved','sold'), default='available')
    image_url = Column(String)"
```

```bash
memory publish code "src/lib/auth.ts -- verifyToken and signToken functions" \
  --tags auth,jwt,typescript --ref EPIC-001 \
  --detail "import jwt from 'jsonwebtoken';

export interface AuthPayload {
  userId: string;
  role: 'admin' | 'user';
}

export function verifyToken(token: string): AuthPayload {
  return jwt.verify(token, process.env.JWT_SECRET!) as AuthPayload;
}

export function signToken(payload: Omit<AuthPayload, 'iat'>): string {
  return jwt.sign(payload, process.env.JWT_SECRET!, { expiresIn: '24h' });
}"
```

```bash
memory publish code "src/api/cats.py -- Cat CRUD endpoints (FastAPI router)" \
  --tags api,cats,fastapi,router --ref EPIC-002 \
  --detail "from fastapi import APIRouter, Query
from src.models.cat import Cat
from src.database import get_db

router = APIRouter(prefix='/api/v1/cats', tags=['cats'])

@router.get('/')
async def list_cats(
    breed: str | None = None,
    min_price: float | None = Query(None, alias='minPrice'),
    max_price: float | None = Query(None, alias='maxPrice'),
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db)
) -> dict:
    # Returns: {items: Cat[], total: int, page: int, limit: int}
    ..."
```

### `interface` -- API contracts with exact request/response shapes

Include the **exact JSON shape** so consumers can build against it without reading your code.

```bash
memory publish interface "GET /api/v1/cats -- paginated cat listing" \
  --tags api,cats,rest --ref EPIC-002 \
  --detail "Request:  GET /api/v1/cats?breed=persian&minPrice=100&maxPrice=500&page=1&limit=20
Headers:  Authorization: Bearer <jwt>  (optional, required for admin fields)

Response 200:
{
  \"items\": [
    {
      \"id\": \"uuid\",
      \"name\": \"Whiskers\",
      \"breed\": \"persian\",
      \"age\": 3,
      \"price\": 299.99,
      \"status\": \"available\",
      \"imageUrl\": \"https://cdn.example.com/cats/uuid.jpg\",
      \"createdAt\": \"2026-03-28T08:00:00Z\"
    }
  ],
  \"total\": 42,
  \"page\": 1,
  \"limit\": 20
}

Response 404: {\"detail\": \"Cat not found\"}"
```

### `artifact` -- What you created (file list + summary)

```bash
memory publish artifact "Set up FastAPI backend with cat CRUD" \
  --tags backend,fastapi,setup --ref EPIC-002 \
  --detail "Files created:
  src/main.py          -- FastAPI app entry point, mounts routers
  src/database.py      -- SQLAlchemy engine + get_db dependency
  src/models/cat.py    -- Cat model (see code memory)
  src/api/cats.py      -- CRUD router (see code memory)
  src/api/auth.py      -- JWT middleware
  alembic/             -- Migration scripts
  tests/test_cats.py   -- 12 tests, all passing

Run: uvicorn src.main:app --reload
Test: pytest tests/ -v"
```

### `decision` -- Architectural choice with the WHY

```bash
memory publish decision "JWT stateless auth over server sessions" \
  --tags auth,jwt,architecture --ref EPIC-001 \
  --detail "Why: multiple services need to verify auth independently.
Token stored in: localStorage (frontend)
Expiry: 24h with refresh token rotation
Secret: JWT_SECRET env var
Library: python-jose (backend), jsonwebtoken (frontend)"
```

### `convention` -- Coding patterns to follow

```bash
memory publish convention "Error response format" \
  --tags api,errors,convention --ref EPIC-001 \
  --detail "All API errors return:
{
  \"detail\": \"Human-readable message\",
  \"code\": \"MACHINE_READABLE_CODE\",
  \"errors\": [{\"field\": \"email\", \"message\": \"Invalid format\"}]  // optional
}

HTTP status codes:
  400 -- validation error
  401 -- missing/invalid auth
  403 -- insufficient permissions
  404 -- resource not found
  409 -- conflict (duplicate)"
```

### `warning` -- Things that will break if ignored

```bash
memory publish warning "cats.status has a CHECK constraint" \
  --tags database,cats,migration --ref EPIC-002 \
  --detail "The 'status' column uses a PostgreSQL CHECK constraint:
  CHECK (status IN ('available', 'reserved', 'sold'))

Adding new statuses requires a migration:
  alembic revision --autogenerate -m 'add pending status'
  alembic upgrade head

Without migration, INSERT/UPDATE will fail with:
  psycopg2.errors.CheckViolation"
```

## When to Query

### At the start of your work -- ALWAYS do this first

```bash
memory context <your-room-id> --keywords <terms-from-your-brief>
```

### Need exact code to import

```bash
memory query --kind code --tags auth
memory search "cat model sqlalchemy"
```

### Need API contracts to consume

```bash
memory query --kind interface --tags cats,api
```

### Check what files exist

```bash
memory search "src/models"
memory query --kind code --ref EPIC-001
```

## Command Reference

```
memory publish <kind> <summary> [options]
  Kinds: code, artifact, decision, interface, convention, warning
  --tags tag1,tag2       Tags (comma-separated)
  --ref EPIC-001         Epic/task reference
  --detail "..."         THE CODE -- full snippets, file contents, JSON shapes
  --supersedes mem-id    Replace an older entry

memory query [options]
  --kind code            Filter by kind
  --tags auth,api        Filter by tags (OR match)
  --ref EPIC-001         Filter by reference
  --exclude-room room-id Exclude a room's entries
  --last N               Last N entries only

memory search "<text>"
  --kind code            Filter by kind
  --max N                Max results (default 10)

memory context <room-id>
  --keywords auth,cats   Filter by relevance

memory list [--kind code]
```

## Rules

1. **Always include `--detail` with actual code** -- summaries alone don't help agents code
2. **Publish `code` entries for every file** other rooms might import
3. **Include exact function signatures and types** in `--detail`
4. **Publish `interface` with full request/response JSON** for every API endpoint
5. **Query `memory context` at the start** of every task
6. **Use `--supersedes` when you change a file** -- don't leave stale code references
