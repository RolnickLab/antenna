import { EntityFieldValues } from './types'

export const convertToServerFieldValues = (fieldValues: EntityFieldValues) => {
  return {
    description: fieldValues.description,
    name: fieldValues.name,
    project: fieldValues.projectId,
    ...(fieldValues.customFields ?? {}),
  }
}
