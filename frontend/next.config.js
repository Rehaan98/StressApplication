/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },
  // NOTE: @xenova/transformers is intentionally NOT bundled (an earlier
  // IgnorePlugin approach still left a chunk that threw at load time in
  // Brave). It ships as a prebuilt ESM file in public/vendor/, imported
  // natively by src/lib/localTranscription.ts. The npm package remains a
  // dependency only so scripts/fetch-stt-assets.sh can copy version-matched
  // WASM binaries from it.
}

module.exports = nextConfig
