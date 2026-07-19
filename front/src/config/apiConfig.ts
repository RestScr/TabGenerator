const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

export const apiConfig = {
  baseUrl: (configuredBaseUrl || 'http://127.0.0.1:8002/api/v1').replace(/\/$/, ''),
  jobPollIntervalMs: 2_000,
  // Demucs (two passes) + GAPS (three candidates) can take 10–12 minutes
  // on CPU for a full-length song. Keep polling long enough for the job to
  // finish instead of showing a client-side timeout while it is still running.
  jobPollAttempts: 900,
} as const
