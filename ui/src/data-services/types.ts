export interface Deployment {
  id: string
  name: string
  numDetections: number
  numEvents: number
  numImages: number
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

export interface Session {
  avgTemp: string
  datespan: string
  deployment: string
  durationLabel: string
  durationMinutes: number
  id: string
  images: { src: string; alt?: string }[]
  numDetections: number
  numImages: number
  numOccurrences: number
  numSpecies: number
  timespan: string
  timestamp: Date
}
