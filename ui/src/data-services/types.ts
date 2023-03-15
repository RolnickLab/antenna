export interface Deployment {
  id: string
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
  id: string
  images: { src: string; alt?: string }[]
  sessionId: string
  sessionTimespan: string
  timestamp: Date
}
