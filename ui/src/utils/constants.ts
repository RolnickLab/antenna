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

export const SCORE_THRESHOLDS = {
  WARNING: 0.8,
  ALERT: 0.6,
}

/**
 * Calculate dynamic score thresholds based on a project's score threshold.
 *
 * This creates relative ranges that provide meaningful visual feedback:
 * - Gray: Below the project threshold
 * - Red: Lower range above project threshold (0% to 10% above threshold)
 * - Orange: Middle range above project threshold (10% to 60% above threshold)
 * - Green: Upper range above project threshold (above 60% of range above threshold)
 *
 * @param projectScoreThreshold - The project's configured score threshold (e.g., 0.6)
 * @returns Object with ALERT and WARNING thresholds for use in styling logic
 *
 * @example
 * // With project threshold of 0.6:
 * const thresholds = calculateDynamicScoreThresholds(0.6)
 * // Returns: { ALERT: 0.64, WARNING: 0.84 }
 * // Gray: < 0.6, Red: 0.6-0.64, Orange: 0.64-0.84, Green: >= 0.84
 */
export const calculateDynamicScoreThresholds = (
  projectScoreThreshold?: number
): { ALERT: number; WARNING: number } => {
  const baseThreshold = projectScoreThreshold ?? SCORE_THRESHOLDS.WARNING // Default to 0.8 if no project threshold

  // Create relative thresholds within the range above the project threshold
  const visibleRangeAboveThreshold = 1.0 - baseThreshold

  // Red: lower 10% above baseThreshold
  const alertThreshold = baseThreshold + visibleRangeAboveThreshold * 0.1

  // Orange: middle range (10% to 60% of range above baseThreshold)
  const warningThreshold = baseThreshold + visibleRangeAboveThreshold * 0.6

  return {
    ALERT: alertThreshold, // Red: baseThreshold to alertThreshold
    WARNING: warningThreshold, // Orange: alertThreshold to warningThreshold
    // Green: above warningThreshold
  }
}

/**
 * Get the appropriate color class for a score based on dynamic thresholds.
 *
 * @param score - The score to evaluate (0-1)
 * @param projectScoreThreshold - The project's configured score threshold
 * @returns 'neutral' (gray), 'alert' (red), 'warning' (orange), or 'success' (green)
 */
export const getScoreColorClass = (
  score: number,
  projectScoreThreshold?: number
): 'neutral' | 'alert' | 'warning' | 'success' => {
  const baseThreshold = projectScoreThreshold ?? SCORE_THRESHOLDS.WARNING

  // Gray: below project threshold
  if (score < baseThreshold) return 'neutral'

  const thresholds = calculateDynamicScoreThresholds(projectScoreThreshold)

  if (score < thresholds.ALERT) return 'alert'
  if (score < thresholds.WARNING) return 'warning'
  return 'success'
}
