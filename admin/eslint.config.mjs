import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/scm/:path*',
        destination: 'http://localhost:8000/scm/:path*',
      },
    ];
  },
};

export default nextConfig;
