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

  // TODO: Investigate why settings are not being saved
  if (fieldValues.defaultFilters) {
    data.append(
      'settings',
      JSON.stringify({
        default_filters_score_threshold:
          fieldValues.defaultFilters.scoreThreshold,
        default_filters_include_taxa: fieldValues.defaultFilters.includeTaxa,
        default_filters_exclude_taxa: fieldValues.defaultFilters.excludeTaxa,
      })
    )
  }

  return data
}
