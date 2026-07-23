import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { ServerBulkIdentificationResponse } from 'data-services/models/identification'
import { getAuthHeader } from 'data-services/utils'
import { useEffect, useRef, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useUser } from 'utils/user/userContext'
import { IdentificationFieldValues } from './types'
import { convertToServerFieldValues } from './useCreateIdentification'

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
  const successResetTimeout = useRef<ReturnType<typeof setTimeout>>()

  const { mutateAsync, isLoading, isSuccess, isError, reset } = useMutation({
    mutationFn: async (values: IdentificationFieldValues[]) => {
      const { data } = await axios.post<ServerBulkIdentificationResponse>(
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
        successResetTimeout.current = setTimeout(() => reset(), SUCCESS_TIMEOUT)
      }
    },
  })

  // Clear the retry state when the selection changes. Keyed on the IDs, not
  // their count, so swapping to a same-sized selection also clears it.
  const selectionKey = occurrenceIds.join(',')
  useEffect(() => {
    setLastAttempt(undefined)
  }, [selectionKey])

  // Cancel a pending success reset when the hook unmounts.
  useEffect(() => () => clearTimeout(successResetTimeout.current), [])

  const numRejected = lastAttempt?.failed.length
  const partialError = numRejected
    ? lastAttempt && lastAttempt.total > 1
      ? translate(STRING.MESSAGE_IDENTIFICATIONS_REJECTED, {
          numRejected,
          total: lastAttempt.total,
        })
      : translate(STRING.MESSAGE_IDENTIFICATION_REJECTED)
    : undefined
  // A rejected whole request (permission denied, invalid batch) surfaces here.
  const requestError = isError
    ? translate(STRING.MESSAGE_IDENTIFICATION_REJECTED)
    : undefined
  // The newest failure wins: a retry rejected at the request level replaces
  // the partial-failure message left over from the previous attempt.
  const error = requestError ?? partialError

  return {
    // A partial failure is still a successful request, so only report success
    // once every item landed.
    isSuccess: isSuccess && !error,
    isLoading,
    error,
    createIdentifications: async (params: IdentificationFieldValues[]) => {
      // On a retry, resend only the items that failed last time.
      const toSubmit = partialError && lastAttempt ? lastAttempt.failed : params
      // A success reset scheduled by an earlier submission must not fire while
      // this one is in flight.
      clearTimeout(successResetTimeout.current)
      try {
        await mutateAsync(toSubmit)
      } catch {
        // A rejected request is surfaced through `error`; swallow it here so the
        // caller's click handler does not see an unhandled rejection.
      }
    },
  }
}
