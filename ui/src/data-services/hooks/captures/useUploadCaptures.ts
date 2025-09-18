import { useQueryClient } from '@tanstack/react-query'
import { API_ROUTES, SUCCESS_TIMEOUT } from 'data-services/constants'
import { useState } from 'react'
import { useUploadCapture } from './useUploadCapture'

type Result = PromiseSettledResult<any>

const isRejected = (result: Result) => result.status === 'rejected'

export const useUploadCaptures = (onSuccess?: () => void) => {
  const queryClient = useQueryClient()
  const [results, setResults] = useState<Result[]>()
  const { uploadCapture, isLoading, isSuccess, reset } = useUploadCapture(
    () => {
      setTimeout(() => {
        reset()
      }, SUCCESS_TIMEOUT)
    }
  )

  const error = results?.some(isRejected)
    ? 'Not all images could be uploaded, please retry.'
    : undefined

  return {
    isLoading,
    isSuccess,
    error,
    uploadCaptures: async (params: {
      projectId: string
      deploymentId: string
      files: File[]
    }) => {
      const promises = params.files
        .filter((_, index) => {
          if (error) {
            // Only retry rejected requests
            return results?.[index]?.status === 'rejected'
          }

          return true
        })
        .map((file) =>
          uploadCapture({
            projectId: params.projectId,
            deploymentId: params.deploymentId,
            file,
          })
        )

      setResults(undefined)
      const updatesResults = await Promise.allSettled(promises)
      setResults(updatesResults)

      if (!updatesResults?.some(isRejected)) {
        queryClient.invalidateQueries([API_ROUTES.CAPTURES])
        queryClient.invalidateQueries([API_ROUTES.DEPLOYMENTS])
        queryClient.invalidateQueries([API_ROUTES.SUMMARY])
        queryClient.invalidateQueries([API_ROUTES.PROJECTS, params.projectId])
        onSuccess?.()
      }
    },
  }
}
