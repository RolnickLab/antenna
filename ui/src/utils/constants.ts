export const APP_ROUTES = {
  /* Static app routes */
  CODE_OF_CONDUCT: '/code-of-conduct',
  HOME: '/',
  LOGIN: '/auth/login',
  PROJECTS: '/projects',
  RESET_PASSWORD_CONFIRM: '/auth/reset-password-confirm',
  RESET_PASSWORD: '/auth/reset-password',
  SIGN_UP: '/auth/sign-up',
  TERMS_OF_SERVICE: '/terms-of-service',

  /* Dynamic app routes */
  PROJECT_DETAILS: (params: { projectId: string }) =>
    `/projects/${params.projectId}`,

  SUMMARY: (params: { projectId: string }) =>
    `/projects/${params.projectId}/summary`,

  COLLECTIONS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/collections`,

  COLLECTION_DETAILS: (params: { projectId: string; collectionId: string }) =>
    `/projects/${params.projectId}/collections/${params.collectionId}`,

  EXPORTS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/exports`,

  EXPORT_DETAILS: (params: { projectId: string; exportId: string }) =>
    `/projects/${params.projectId}/exports/${params.exportId}`,

  PROCESSING_SERVICES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/processing-services`,

  PROCESSING_SERVICE_DETAILS: (params: {
    projectId: string
    processingServiceId: string
  }) =>
    `/projects/${params.projectId}/processing-services/${params.processingServiceId}`,

  ALGORITHMS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/algorithms`,

  PIPELINES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/pipelines`,

  ALGORITHM_DETAILS: (params: { projectId: string; algorithmId: string }) =>
    `/projects/${params.projectId}/algorithms/${params.algorithmId}`,

  PIPELINE_DETAILS: (params: { projectId: string; pipelineId: string }) =>
    `/projects/${params.projectId}/pipelines/${params.pipelineId}`,

  SITES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/sites`,

  DEVICES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/devices`,

  GENERAL: (params: { projectId: string }) =>
    `/projects/${params.projectId}/general`,

  STORAGE: (params: { projectId: string }) =>
    `/projects/${params.projectId}/storage`,

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
}

export const API_MAX_UPLOAD_SIZE = 1024 * 1024 * 30 // 30MB

export const LANDING_PAGE_URL = 'https://insectai.org/'

export const LANDING_PAGE_WAITLIST_URL = 'https://insectai.org/waitlist'

export const SCORE_THRESHOLDS = {
  WARNING: 0.8,
  ALERT: 0.6,
}
