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

  ALGORITHM_DETAILS: (params: { projectId: string; algorithmId: string }) =>
    `/projects/${params.projectId}/algorithms/${params.algorithmId}`,

  ALGORITHMS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/algorithms`,

  CAPTURES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/captures`,

  COLLECTIONS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/collections`,

  DEFAULT_FILTERS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/default-filters`,

  DEPLOYMENT_DETAILS: (params: { projectId: string; deploymentId: string }) =>
    `/projects/${params.projectId}/deployments/${params.deploymentId}`,

  DEPLOYMENTS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/deployments`,

  DEVICES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/devices`,

  EXPORT_DETAILS: (params: { projectId: string; exportId: string }) =>
    `/projects/${params.projectId}/exports/${params.exportId}`,

  EXPORTS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/exports`,

  GENERAL: (params: { projectId: string }) =>
    `/projects/${params.projectId}/general`,

  JOB_DETAILS: (params: { projectId: string; jobId: string }) =>
    `/projects/${params.projectId}/jobs/${params.jobId}`,

  JOBS: (params: { projectId: string }) => `/projects/${params.projectId}/jobs`,

  OCCURRENCE_DETAILS: (params: { projectId: string; occurrenceId: string }) =>
    `/projects/${params.projectId}/occurrences/${params.occurrenceId}`,

  OCCURRENCES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/occurrences`,

  PIPELINE_DETAILS: (params: { projectId: string; pipelineId: string }) =>
    `/projects/${params.projectId}/pipelines/${params.pipelineId}`,

  PIPELINES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/pipelines`,

  PROCESSING: (params: { projectId: string }) =>
    `/projects/${params.projectId}/processing`,

  PROCESSING_SERVICE_DETAILS: (params: {
    projectId: string
    processingServiceId: string
  }) =>
    `/projects/${params.projectId}/processing-services/${params.processingServiceId}`,

  PROCESSING_SERVICES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/processing-services`,

  PROJECT_DETAILS: (params: { projectId: string }) =>
    `/projects/${params.projectId}`,

  SESSION_DETAILS: (params: { projectId: string; sessionId: string }) =>
    `/projects/${params.projectId}/sessions/${params.sessionId}`,

  SESSIONS: (params: { projectId: string }) =>
    `/projects/${params.projectId}/sessions`,

  SITES: (params: { projectId: string }) =>
    `/projects/${params.projectId}/sites`,

  STORAGE: (params: { projectId: string }) =>
    `/projects/${params.projectId}/storage`,

  SUMMARY: (params: { projectId: string }) =>
    `/projects/${params.projectId}/summary`,

  TAXA: (params: { projectId: string }) => `/projects/${params.projectId}/taxa`,

  TAXON_DETAILS: (params: { projectId: string; taxonId: string }) =>
    `/projects/${params.projectId}/taxa/${params.taxonId}`,
}

export const API_MAX_UPLOAD_SIZE = 1024 * 1024 * 30 // 30MB

export const LANDING_PAGE_URL = 'https://insectai.org/'

export const LANDING_PAGE_WAITLIST_URL = 'https://insectai.org/waitlist'

export const DOCS_URL =
  import.meta.env.VITE_DOCS_URL ?? 'https://rolnicklab.github.io/antenna-docs'

export const DOCS_LINKS = {
  CONFIGURING_DATA_SOURCE: `${DOCS_URL}/sections/user-guide/uploading-data/#configuring-a-data-source`,
  EXPORTING_DATA: `${DOCS_URL}/sections/user-guide/exporting-data`,
  PROCESSING_DATA: `${DOCS_URL}/sections/user-guide/processing-data`,
  PROJECT_CREATION: `${DOCS_URL}/sections/user-guide/project-creation`,
  UPLOADING_DATA: `${DOCS_URL}/sections/user-guide/uploading-data`,
  VALIDATING_DATA: `${DOCS_URL}/sections/user-guide/validating-data`,
}

export const SCORE_THRESHOLDS = {
  WARNING: 0.8,
  ALERT: 0.6,
}
