export const JOB_TYPE_ML = 'ml'
export const JOB_TYPE_TRAIN_CLASSIFIER = 'train_classifier'

export interface JobFormValues {
  algorithmKey?: string
  delay: number
  jobType: string
  minPerSpecies?: number | string
  name: string
  occurrenceSet?: string
  pipeline?: string
  sourceImage?: string
  sourceImages?: string
  startNow?: boolean
  testFraction?: number | string
}
