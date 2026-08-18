import type { NextConfig } from "next";

const isDocker = process.env.DOCKER === "1";
const isVercel = process.env.VERCEL === "1";

const nextConfig: NextConfig = {
  // Docker image uses the standalone server. Vercel is a static host for this
  // monorepo (the Next app is in apps/web, not the repo root).
  ...(isDocker ? { output: "standalone" as const } : {}),
  ...(isVercel ? { output: "export" as const, images: { unoptimized: true } } : {}),
};

export default nextConfig;
