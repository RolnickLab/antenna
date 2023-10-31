export const API_URL =
  process.env.NODE_ENV === 'test' ? 'http://localhost:3000/api/v2' : '/api/v2'

export const API_ROUTES = {
  CAPTURES: 'captures',
  COLLECTIONS: 'captures/collections',
  DEPLOYMENTS: 'deployments',
  IDENTIFICATIONS: 'identifications',
  JOBS: 'jobs',
  LOGIN: 'auth/token/login',
  LOGOUT: 'auth/token/logout',
  ME: 'users/me',
  OCCURRENCES: 'occurrences',
  PAGES: 'pages',
  PROJECTS: 'projects',
  SESSIONS: 'events',
  SPECIES: 'taxa',
  SUMMARY: 'status/summary',
  USERS: 'users',
}

export const STATUS_CODES = {
  FORBIDDEN: 403,
}
