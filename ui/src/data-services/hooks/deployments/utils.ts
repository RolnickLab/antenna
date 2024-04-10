import { DeploymentFieldValues } from 'data-services/models/deployment-details'

export const convertToFormData = (fieldValues: DeploymentFieldValues) => {
  const data = new FormData()

  Object.entries({
    data_source_id: fieldValues.dataSourceId,
    description: fieldValues.description,
    device_id: fieldValues.deviceId,
    name: fieldValues.name,
    latitude: fieldValues.latitude,
    longitude: fieldValues.longitude,
    research_site_id: fieldValues.siteId,
  }).forEach(([key, value]) => {
    if (value !== undefined) {
      data.append(key, `${value}`)
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
