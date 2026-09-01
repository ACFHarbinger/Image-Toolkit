// Next.js config — not the primary framework here; kept as an alternate
// React-rendered surface over the frameworks/react/ island components, the
// Not part of the default build/deploy pipeline; reachable only via
// `npm run next:*`.
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  pageExtensions: ["tsx", "ts"],
};

export default nextConfig;
