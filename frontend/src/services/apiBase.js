export const getApiBase = (env) => env.VITE_API_BASE ?? (env.PROD ? '' : 'http://localhost:8000')
