import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/about",
        destination: "/about/",
        permanent: false,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/about/",
        destination: "/about/index.html",
      },
    ];
  },
};

export default nextConfig;
