import { EntityFieldValues } from './types'

export const convertToServerFieldValues = (fieldValues: EntityFieldValues) => ({
  description: fieldValues.description,
  name: fieldValues.name,
  project: fieldValues.projectId,
})
