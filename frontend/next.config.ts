import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // In Next.js, rewrites are evaluated at build time. 
    // During docker compose build, process.env.BACKEND_URL is not set.
    // We use "http://backend:8000" for production (Docker) and localhost for dev.
    const backendUrl = process.env.BACKEND_URL || (process.env.NODE_ENV === "production" ? "http://backend:8000" : "http://localhost:8000");
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  // Disable strict mode for better development experience with external APIs
  reactStrictMode: false,
};

export default nextConfig;
