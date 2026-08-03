/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const apiTarget = process.env.INTERNAL_API_URL || "http://api:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;