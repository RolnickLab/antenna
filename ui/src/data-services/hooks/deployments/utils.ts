import { DeploymentFieldValues } from 'data-services/models/deployment-details'

export const convertToFormData = (fieldValues: DeploymentFieldValues) => {
  const data = new FormData()

  Object.entries({
    data_source_id: fieldValues.dataSourceId,
    data_source_subdir: fieldValues.dataSourceSubdir,
    data_source_regex: fieldValues.dataSourceRegex,
    description: fieldValues.description,
    device_id: fieldValues.deviceId,
    name: fieldValues.name,
    latitude: fieldValues.latitude,
    longitude: fieldValues.longitude,
    research_site_id: fieldValues.siteId,
  }).forEach(([key, value]) => {
    if (value !== undefined) {
      // Convert null to empty string to signal "clear this field" (matches image field pattern)
      data.append(key, value === null ? '' : `${value}`)
    }
  })

  if (fieldValues.projectId) {
    data.append('project_id', fieldValues.projectId)
  }

  if (fieldValues.image) {
    data.append('image', fieldValues.image, fieldValues.image.name)
  } else if (fieldValues.image === null) {
    data.append('image', '')
  }

  return data
}
