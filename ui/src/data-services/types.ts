export interface Deployment {
  name: string
  numDetections: number
  numEvents: number
  numSourceImages: number
}

export interface Occurrence {
  appearanceDuration: string
  appearanceTimespan: string
  categoryLabel: string
  deployment: string
  deploymentLocation: string
  familyLabel: string
  sessionId: string
  sessionTimespan: string
}
