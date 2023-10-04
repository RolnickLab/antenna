import { useEffect, useState } from 'react'
import { UseFormSetError } from 'react-hook-form'
import { parseServerError } from 'utils/parseServerError/parseServerError'

export const useFormError = ({
  error,
  setFieldError,
}: {
  error: unknown
  setFieldError?: UseFormSetError<any>
}) => {
  const [errorMessage, setErrorMessage] = useState<string | undefined>()

  useEffect(() => {
    if (!error) {
      setErrorMessage(undefined)
    } else {
      const { message, fieldErrors } = parseServerError(error)
      setErrorMessage(message)
      fieldErrors.forEach((error) => {
        setFieldError?.(
          error.key,
          { message: error.message },
          { shouldFocus: true }
        )
      })
    }
  }, [error])

  return errorMessage
}
