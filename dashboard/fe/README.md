# Agent OS Command Center Dashboard

This is the Next.js frontend for the Agent OS Command Center.

## Getting Started

First, install dependencies:

```bash
bun install
```

Then, run the development server with mock API:

```bash
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Backend Integration

By default, the dashboard uses a mock API layer located in `src/app/api/`.

### Swapping to Real Backend

To connect the dashboard to a real backend (e.g., a FastAPI server), set the `NEXT_PUBLIC_API_BASE_URL` environment variable:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:3366/api bun run dev
```

Or create a `.env.local` file:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:3366/api
```

When this variable is set, the `api-client.ts` will redirect all calls to the specified URL instead of the local `/api` routes.

### Mock Realtime Toggle

The dashboard includes a mock realtime simulation. You can toggle this behavior in `src/lib/stores/uiStore.ts` or through the settings panel (if implemented).

## Production Build & Static Export

To create a production build with static export:

```bash
bun run build
```

The output will be in the `out/` directory. Note that static export requires `generateStaticParams` for all dynamic routes, which have been pre-configured with mock data.

