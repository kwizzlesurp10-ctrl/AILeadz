/** @type {import('next').NextConfig} */
const LIVEBENCH_API_URL = process.env.LIVEBENCH_API_URL;

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@clawwork/db"],
  ...(LIVEBENCH_API_URL && {
    async rewrites() {
      return [
        { source: "/api/livebench/:path*", destination: `${LIVEBENCH_API_URL}/api/:path*` },
        { source: "/ws", destination: `${LIVEBENCH_API_URL}/ws` },
      ];
    },
  }),
};

module.exports = nextConfig;
