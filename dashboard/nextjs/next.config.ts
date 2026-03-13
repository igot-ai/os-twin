import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },
  // Trailing slash for cleaner static file mapping
  trailingSlash: false,
};

export default nextConfig;
