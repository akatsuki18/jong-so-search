import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.NODE_ENV === 'development'
          ? 'http://localhost:8000/:path*'  // ローカル開発時
          : '/api/:path*'  // プロダクション環境（Vercel）
      }
    ]
  }
};

export default nextConfig;
