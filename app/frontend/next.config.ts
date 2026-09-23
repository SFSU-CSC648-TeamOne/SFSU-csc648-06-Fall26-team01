import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/about",
        destination: "/about/index.html",
      },
    ];
  },
};

export default nextConfig;
