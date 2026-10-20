import { parseServerError } from 'utils/parseServerError/parseServerError'

// The form shows only the name, so errors on the other fields (for example an
// occurrence deleted since the page loaded) go in the banner. This endpoint reports
// failures per field, so the generic message is axios's status text whenever field
// errors are present, and is left out then.
export const getFormErrors = (
  error: unknown
): { formError?: string; nameError?: string } => {
  if (!error) {
    return {}
  }
  const { message, fieldErrors } = parseServerError(error)
  const nameError = fieldErrors.find((e) => e.key === 'name')?.message
  const otherErrors = fieldErrors
    .filter((e) => e.key !== 'name')
    .map((e) => e.message)

  return {
    nameError,
    formError: otherErrors.length
      ? otherErrors.join(' ')
      : fieldErrors.length
      ? undefined
      : message,
  }
}
