# Railway: two services from one repo

Both services use the same Dockerfile with different PROCESS_TYPE values.

Service 1 — API
  Root directory: backend
  PROCESS_TYPE=api
  Generate a public domain. This is what the frontend calls.

Service 2 — Worker
  Root directory: backend
  PROCESS_TYPE=worker
  No public domain needed. It only polls Temporal.

Shared environment variables for both:
  ANTHROPIC_API_KEY
  ANTHROPIC_MODEL=claude-sonnet-4-6
  TEMPORAL_ADDRESS=<namespace>.<account>.tmprl.cloud:7233
  TEMPORAL_NAMESPACE=<your-namespace>
  TEMPORAL_TLS_CERT / TEMPORAL_TLS_KEY  (from Temporal Cloud)
  CORS_ORIGINS=https://<your-app>.vercel.app
