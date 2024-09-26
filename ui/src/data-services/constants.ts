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
  RESET_PASSWORD: 'users/reset_password',
  RESET_PASSWORD_CONFIRM: 'users/reset_password_confirm',
  SESSIONS: 'events',
  SITES: 'deployments/sites',
  SPECIES: 'taxa',
  TAXA_OBSERVED: 'taxa/observed',
  STORAGE: 'storage',
  SUMMARY: 'status/summary',
  USERS: 'users',
}

export const STATUS_CODES = {
  FORBIDDEN: 403,
}

export const SUCCESS_TIMEOUT = 1000 // Reset success after 1 second
