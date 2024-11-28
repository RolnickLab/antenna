export const APP_ROUTES = {
  /* Static app routes */
  HOME: '/',
  LOGIN: '/auth/login',
  SIGN_UP: '/auth/sign-up',
  RESET_PASSWORD: '/auth/reset-password',
  RESET_PASSWORD_CONFIRM: '/auth/reset-password-confirm',
  TERMS_OF_SERVICE: '/terms-of-service',
  PROJECTS: '/projects',

  /* Dynamic app routes */
  PROJECT_DETAILS: (params: { projectId: string }) =>
    `/projects/${params.projectId}`,

  DEPLOYMENTS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/deployments`,

  DEPLOYMENT_DETAILS: (params: { projectId: string; deploymentId: string }) =>
    `/projects/${params.projectId}/deployments/${params.deploymentId}`,

  JOBS: (params: { projectId: string }) => `/projects/${params.projectId}/jobs`,

  JOB_DETAILS: (params: { projectId: string; jobId: string }) =>
    `/projects/${params.projectId}/jobs/${params.jobId}`,

  SESSIONS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/sessions`,

  SESSION_DETAILS: (params: { projectId: string; sessionId: string }) =>
    `/projects/${params.projectId}/sessions/${params.sessionId}`,

  OCCURRENCES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/occurrences`,

  OCCURRENCE_DETAILS: (params: { projectId: string; occurrenceId: string }) =>
    `/projects/${params.projectId}/occurrences/${params.occurrenceId}`,

  TAXA: (params: { projectId: string }) => `/projects/${params.projectId}/taxa`,

  TAXON_DETAILS: (params: { projectId: string; taxonId: string }) =>
    `/projects/${params.projectId}/taxa/${params.taxonId}`,

  COLLECTIONS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/collections`,

  COLLECTION_DETAILS: (params: { projectId: string; collectionId: string }) =>
    `/projects/${params.projectId}/collections/${params.collectionId}`,
}

export const API_MAX_UPLOAD_SIZE = 1024 * 1024 * 30 // 30MB

export const LANDING_PAGE_URL = 'https://insectai.org/'

export const LANDING_PAGE_WAITLIST_URL = 'https://insectai.org/waitlist'
