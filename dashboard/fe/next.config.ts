import type { NextConfig } from "next";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000';

const nextConfig: NextConfig = {
  output: 'export',
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
