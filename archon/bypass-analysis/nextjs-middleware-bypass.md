# CVE-2025-29927 — Next.js Middleware Authentication Bypass

**Cluster ID**: nextjs-middleware-auth
**Advisory**: CVE-2025-29927
**Bypass Verdict**: **not-applicable**

## Patch Summary

CVE-2025-29927 allowed attackers to bypass Next.js middleware-based authentication by sending a crafted `x-middleware-subrequest` header, causing the middleware layer to skip execution entirely. The fix (in Next.js >= 15.2.3 / 14.2.25) validates and strips that header at the edge.

## Findings

### 1. No Next.js Middleware Is Used

No `middleware.ts` or `middleware.js` file exists anywhere in `dashboard/fe/` or `dashboard/fe/src/`. The project does **not** use Next.js middleware for authentication or any other purpose. This means CVE-2025-29927 has no exploitable surface in this application regardless of version.

### 2. Authentication Architecture

Authentication is handled entirely on the **server side** by the Python FastAPI backend:

- **Login**: The React client sends an API key to `POST /api/auth/token` on the FastAPI backend, which returns a session cookie.
- **Session check**: On mount, the client calls `GET /api/auth/me` with `credentials: 'include'` to verify the cookie.
- **Client-side gate**: `AuthOverlay` renders a blocking overlay when `isAuthenticated` is false. This is a UX convenience only — the actual auth enforcement is backend-side.

The frontend has **zero API route handlers** (`dashboard/fe/src/app/api/` does not exist). All `/api/*` requests are proxied to FastAPI via `next.config.ts` rewrites (dev mode) or served directly by FastAPI (production static export).

### 3. Static Export in Production

The Next.js config uses `output: 'export'` for production builds. In static export mode:

- **No Next.js server runs in production** — the build produces plain HTML/JS/CSS files.
- **Middleware is never executed** in static exports (middleware requires a Next.js server).
- All API calls go directly to the FastAPI backend, which handles its own auth.

This means even if a `middleware.ts` existed, it would only run in development mode (`next dev`), not in production.

### 4. Installed Version

`package.json` declares `next: "16.2.1"`. This is well beyond the patched versions (15.2.3 / 14.2.25), so the underlying library vulnerability is fixed regardless.

### 5. Bypass Hypotheses

| Vector | Result |
|--------|--------|
| `x-middleware-subrequest` header bypass | **N/A** — no middleware exists |
| Alternate entry points skipping middleware | **N/A** — no middleware to skip |
| Static export changing middleware behavior | Middleware never runs in production (static export) |
| API routes without middleware protection | No Next.js API routes exist; all API auth is FastAPI-side |
| Client-side auth overlay bypass | Cosmetic only; backend rejects unauthenticated API calls independently |

## Risk Assessment

**No risk from CVE-2025-29927.** The application does not use the vulnerable feature (Next.js middleware). Authentication is enforced server-side by FastAPI. The client-side auth overlay is defense-in-depth UX, not a security boundary.

The only theoretical concern is if someone later adds a `middleware.ts` for auth — but the static export production mode would still prevent it from running.
