import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useEffect, useState } from 'react'
import { useUser } from 'utils/user/userContext'
import { IdentificationFieldValues } from './types'
import { convertToServerFieldValues } from './useCreateIdentification'

interface BulkIdentificationResult {
  index: number
  occurrence_id: number
  status: 'created' | 'error'
  id?: number
  errors?: Record<string, string[]>
}

interface BulkIdentificationResponse {
  created_count: number
  error_count: number
  results: BulkIdentificationResult[]
}

// Records the outcome of the last submission so a retry can resend only the
// items that failed, and so the error message can report how many did.
interface LastAttempt {
  failed: IdentificationFieldValues[]
  total: number
}

/**
 * Apply an identification to many occurrences in a single request.
 *
 * The identifications are sent together to the bulk endpoint, which reports a
 * result per item, rather than one request per occurrence. A partial failure
 * (an occurrence deleted since the page loaded, say) leaves the successful items
 * saved and lets a retry resend only the ones that failed.
 */
export const useCreateIdentifications = (
  occurrenceIds: string[],
  onSuccess?: () => void
) => {
  const { user } = useUser()
  const queryClient = useQueryClient()
  const [lastAttempt, setLastAttempt] = useState<LastAttempt>()

  const { mutateAsync, isLoading, isSuccess, isError, reset } = useMutation({
    mutationFn: async (values: IdentificationFieldValues[]) => {
      const { data } = await axios.post<BulkIdentificationResponse>(
        `${API_URL}/${API_ROUTES.IDENTIFICATIONS}/bulk/`,
        { identifications: values.map(convertToServerFieldValues) },
        { headers: getAuthHeader(user) }
      )
      return { data, submitted: values }
    },
    onSuccess: ({ data, submitted }) => {
      // Match failures by the `index` the backend reports against each result,
      // not by position in `results`, so a reordered or sparse response still
      // maps each error back to the right submitted item.
      const failedIndices = new Set(
        data.results
          .filter((result) => result.status === 'error')
          .map((result) => result.index)
      )
      const failed = submitted.filter((_, index) => failedIndices.has(index))
      setLastAttempt({ failed, total: submitted.length })
      queryClient.invalidateQueries([API_ROUTES.IDENTIFICATIONS])
      queryClient.invalidateQueries([API_ROUTES.OCCURRENCES])
      onSuccess?.()
      if (!failed.length) {
        setTimeout(() => reset(), SUCCESS_TIMEOUT)
      }
    },
  })

  // Clear the retry state when the selection changes.
  useEffect(() => {
    setLastAttempt(undefined)
  }, [occurrenceIds.length])

  const numRejected = lastAttempt?.failed.length
  const partialError = numRejected
    ? lastAttempt && lastAttempt.total > 1
      ? `${numRejected}/${lastAttempt.total} updates were rejected, please retry.`
      : 'The update was rejected, please retry.'
    : undefined
  // A rejected whole request (permission denied, invalid batch) surfaces here.
  const requestError = isError
    ? 'The update was rejected, please retry.'
    : undefined
  const error = partialError ?? requestError

  return {
    // A partial failure is still a successful request, so only report success
    // once every item landed.
    isSuccess: isSuccess && !error,
    isLoading,
    error,
    createIdentifications: async (params: IdentificationFieldValues[]) => {
      // On a retry, resend only the items that failed last time.
      const toSubmit = partialError && lastAttempt ? lastAttempt.failed : params
      try {
        await mutateAsync(toSubmit)
      } catch {
        // A rejected request is surfaced through `error`; swallow it here so the
        // caller's click handler does not see an unhandled rejection.
      }
    },
  }
}
