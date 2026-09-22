import type { NextConfig } from "next";

// The dashboard API (FastAPI, `uv run python -m api` in backend/). The browser
// only ever talks to this app's origin; /api/* is forwarded, so the session
// cookie is first-party and needs no cross-site setup. Production puts Caddy
// in front of both instead (Stage 3 slice 5).
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_ORIGIN}/api/:path*` }];
  },
};

export default nextConfig;
