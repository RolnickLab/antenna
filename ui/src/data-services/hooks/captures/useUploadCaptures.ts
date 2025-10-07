import { useQueryClient } from '@tanstack/react-query'
import { API_ROUTES } from 'data-services/constants'
import { useState } from 'react'
import { useUploadCapture } from './useUploadCapture'

type Result = PromiseSettledResult<any>

const isRejected = (result: Result) => result.status === 'rejected'

export const useUploadCaptures = (onSuccess?: () => void) => {
  const queryClient = useQueryClient()
  const [results, setResults] = useState<Result[]>()
  const { uploadCapture, isLoading, isSuccess } = useUploadCapture()

  const error = results?.some(isRejected)
    ? 'Not all images could be uploaded, please retry.'
    : undefined

  return {
    isLoading,
    isSuccess,
    error,
    uploadCaptures: async (params: {
      deploymentId: string
      files: File[]
      processNow?: boolean
      projectId: string
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
            deploymentId: params.deploymentId,
            file,
            processNow: params.processNow,
            projectId: params.projectId,
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
