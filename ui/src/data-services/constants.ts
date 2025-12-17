export const API_URL = '/api/v2'

export const API_ROUTES = {
  ALGORITHM: 'ml/algorithms',
  CAPTURES: 'captures',
  CLASSIFICATIONS: 'classifications',
  COLLECTIONS: 'captures/collections',
  DEPLOYMENTS: 'deployments',
  DEVICES: 'deployments/devices',
  EXPORTS: 'exports',
  IDENTIFICATIONS: 'identifications',
  JOBS: 'jobs',
  LOGIN: 'auth/token/login',
  LOGOUT: 'auth/token/logout',
  ME: 'users/me',
  MEMBERS: (projectId: string) => `projects/${projectId}/members`,
  OCCURRENCES: 'occurrences',
  PAGES: 'pages',
  PIPELINES: 'ml/pipelines',
  PROCESSING_SERVICES: 'ml/processing_services',
  PROJECTS: 'projects',
  RESET_PASSWORD_CONFIRM: 'users/reset_password_confirm',
  RESET_PASSWORD: 'users/reset_password',
  ROLES: 'users/roles',
  SESSIONS: 'events',
  SITES: 'deployments/sites',
  SPECIES: 'taxa',
  STORAGE: 'storage',
  SUMMARY: 'status/summary',
  TAGS: 'tags',
  TAXA_LISTS: 'taxa/lists',
  USERS: 'users',
}

export const STATUS_CODES = {
  FORBIDDEN: 403,
}

export const REFETCH_INTERVAL = 10000 // Refetch every 10 second when polling

export const SUCCESS_TIMEOUT = 1000 // Reset success after 1 second
