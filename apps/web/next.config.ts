import type { NextConfig } from "next";

// Vercel serves Next.js with its own output. `standalone` is only for Docker.
const nextConfig: NextConfig = {
  ...(process.env.DOCKER === "1" ? { output: "standalone" as const } : {}),
};

export default nextConfig;
