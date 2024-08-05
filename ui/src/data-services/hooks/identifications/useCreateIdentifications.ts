import { useEffect, useState } from 'react'
import { IdentificationFieldValues } from './types'
import { useCreateIdentification } from './useCreateIdentification'

export const useCreateIdentifications = (
  params: IdentificationFieldValues[]
) => {
  const [results, setResults] = useState<PromiseSettledResult<any>[]>()
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  const numRejected = results?.filter(
    (result) => result.status === 'rejected'
  ).length

  const error = numRejected
    ? results.length > 1
      ? `${numRejected}/${results.length} updates were rejected, please retry.`
      : 'The update was rejected, please retry.'
    : undefined

  useEffect(() => {
    setResults(undefined)
  }, [params.length])

  return {
    isLoading,
    isSuccess,
    error,
    createIdentifications: async () => {
      const promises = params
        .filter((_, index) => {
          if (error) {
            // Only retry rejected requests
            return results?.[index]?.status === 'rejected'
          }

          return true
        })
        .map((variables) => createIdentification(variables))

      setResults(undefined)
      const result = await Promise.allSettled(promises)
      setResults(result)
    },
  }
}
