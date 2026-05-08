import type { NextConfig } from "next";

const backendBase = process.env.OSTWIN_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3366';
const BACKEND_URL = backendBase.replace(/\/api\/?$/, '');

const isDev = process.env.NODE_ENV === 'development';

const nextConfig: NextConfig = {
  // Only use static export for production builds (next build).
  // In dev mode, dynamic routes work natively without generateStaticParams.
  ...(isDev ? {} : { output: 'export' }),
  images: {
    unoptimized: true,
  },
  // In dev mode (next dev), proxy /api/* requests to the FastAPI backend.
  // In production (static export), the frontend is served by FastAPI directly
  // so /api/* requests go to the same origin — no proxy needed.
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
