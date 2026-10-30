export const JOB_TYPE_ML = 'ml'
export const JOB_TYPE_TRAIN_CLASSIFIER = 'train_classifier'

export const TRAINING_DATA_PROJECT = 'project'
export const TRAINING_DATA_PROJECT_AND_INAT = 'project_inat'
export const TRAINING_DATA_INAT = 'inat'

export interface JobFormValues {
  algorithmKey?: string
  dataSource?: string
  delay: number
  jobType: string
  minPerSpecies?: number | string
  name: string
  occurrenceSet?: string
  pipeline?: string
  sourceImage?: string
  sourceImages?: string
  startNow?: boolean
  taxaList?: string
  testFraction?: number | string
}
