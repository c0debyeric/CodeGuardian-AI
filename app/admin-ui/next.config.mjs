/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output keeps the production Docker image small (~150 MB).
  output: "standalone",
  reactStrictMode: true,
};
export default nextConfig;
