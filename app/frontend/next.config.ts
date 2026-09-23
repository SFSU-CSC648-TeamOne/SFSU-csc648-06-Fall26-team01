import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/about",
        destination: "/about/index.html",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
