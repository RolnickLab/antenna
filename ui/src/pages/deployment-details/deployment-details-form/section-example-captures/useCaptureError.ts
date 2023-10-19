import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { CAPTURE_CONFIG, COPY } from './section-example-captures'

export const useCaptureError = ({
  error,
  file,
  index,
}: {
  error: unknown
  file: File
  index: number
}) => {
  const clientError = (() => {
    if (index >= CAPTURE_CONFIG.NUM_CAPTURES) {
      return COPY.MESSAGE_CAPTURE_LIMIT
    }

    if (file.size > CAPTURE_CONFIG.MAX_SIZE) {
      return translate(STRING.MESSAGE_IMAGE_TOO_BIG)
    }
  })()

  const serverError = (() => {
    if (!error) {
      return undefined
    }

    const { message, fieldErrors } = parseServerError(error)

    if (fieldErrors.length) {
      return fieldErrors.map(({ message }) => message).join('\n')
    }

    return message
  })()

  return {
    isValid: !clientError && !serverError,
    errorMessage: clientError ?? serverError,
    allowRetry: !clientError,
  }
}
