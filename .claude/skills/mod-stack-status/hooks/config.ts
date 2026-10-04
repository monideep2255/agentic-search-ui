// Per-repository settings for mod-stack-status. Every value names where it was found.
export const config = {
  // Backend health path: railway.json, deploy.healthcheckPath.
  apiHealthPath: '/health',
  // Backend local port: env.example (PORT=8000), and the README's uvicorn command, which passes no port and so uses uvicorn's default of 8000.
  apiPort: 8000,
  // Vite dev server port: frontend/vite.config.ts sets no server.port, so Vite's default applies.
  webPort: 5173,
  // PostgreSQL host and port: env.example, USER_DB_URL=postgresql://localhost:5432/...
  dbHost: 'localhost',
  dbPort: 5432,
  pollMs: 30_000,
  probeTimeoutMs: 2_000,
}
