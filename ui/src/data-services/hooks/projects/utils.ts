export const convertToServerFormData = (fieldValues: any) => {
  const data = new FormData()

  if (fieldValues.name) {
    data.append('name', fieldValues.name)
  }
  if (fieldValues.description) {
    data.append('description', fieldValues.description)
  }
  if (fieldValues.image) {
    data.append('image', fieldValues.image, fieldValues.image.name)
  } else if (fieldValues.image === null) {
    data.append('image', '')
  }
  if (fieldValues.isDraft !== undefined) {
    data.append('draft', fieldValues.isDraft)
  }
  if (fieldValues.defaultProcessingPipeline) {
    data.append(
      'settings.default_processing_pipeline_id',
      fieldValues.defaultProcessingPipeline.id
    )
  }

  return data
}
