export const API_URL = '/api/v2'

export const API_ROUTES = {
  CAPTURES: 'captures',
  COLLECTIONS: 'captures/collections',
  DEPLOYMENTS: 'deployments',
  DEVICES: 'deployments/devices',
  IDENTIFICATIONS: 'identifications',
  JOBS: 'jobs',
  LOGIN: 'auth/token/login',
  LOGOUT: 'auth/token/logout',
  ME: 'users/me',
  OCCURRENCES: 'occurrences',
  PAGES: 'pages',
  PIPELINES: 'ml/pipelines',
  PROJECTS: 'projects',
  SESSIONS: 'events',
  SITES: 'deployments/sites',
  SPECIES: 'taxa',
  STORAGE: 'storage',
  SUMMARY: 'status/summary',
  USERS: 'users',
}

export const STATUS_CODES = {
  FORBIDDEN: 403,
}
