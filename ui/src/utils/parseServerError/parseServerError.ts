export const parseServerError = (error: any) => {
  let message = ''
  const fieldErrors: { key: string; message: string }[] = []

  if (error.response?.data && typeof error.response.data === 'object') {
    Object.entries(error.response.data).forEach(([key, details]) => {
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
