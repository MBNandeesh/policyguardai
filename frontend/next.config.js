/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = (process.env.BACKEND_API_URL || 'http://localhost:8000').replace(/\/$/, '')
    return [{ source: '/api/v1/:path*', destination: `${backendUrl}/api/v1/:path*` }]
  },
}

module.exports = nextConfig
