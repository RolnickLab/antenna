import { EntityFieldValues } from './types'

export const convertToServerFieldValues = (fieldValues: EntityFieldValues) => {
  const { description, name, projectId, customFields } = fieldValues

  return {
    ...(description ? { description } : {}),
    ...(name ? { name } : {}),
    project: projectId,
    ...(customFields ?? {}),
  }
}
