/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  transpilePackages: ["@clawwork/db"],
  async rewrites() {
    return [
      { source: "/api/livebench/:path*", destination: "http://localhost:8000/api/:path*" },
      { source: "/ws", destination: "http://localhost:8000/ws" },
    ];
  },
};

module.exports = nextConfig;
