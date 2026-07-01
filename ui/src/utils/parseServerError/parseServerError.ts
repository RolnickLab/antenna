export const parseServerError = (error: any) => {
  let message = ''
  const fieldErrors: { key: string; message: string }[] = []

  const data = error.response?.data

  if (Array.isArray(data)) {
    // DRF serializes `raise ValidationError("some message")` as a top-level
    // JSON list of strings, e.g. ["Deployment must have a data source ..."].
    // Join them into a single message so the reason reaches the user instead
    // of the generic axios "Request failed with status code 400".
    message = data
      .filter((entry) => typeof entry === 'string' && entry.length)
      .join(' ')
  } else if (data && typeof data === 'object') {
    Object.entries(data).forEach(([key, details]) => {
      if (key && details) {
        if (key === 'non_field_errors' || key === 'detail') {
          message = details as string
        } else {
          fieldErrors.push({ key, message: `${(details as string[])[0]}` })
        }
      }
    })
  }

  if (!message.length) {
    message = error.message ?? 'Something went wrong.'
  }

  return { message, fieldErrors }
}
