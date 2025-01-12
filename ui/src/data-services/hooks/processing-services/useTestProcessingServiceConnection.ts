import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios, { AxiosError } from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { APIValidationError } from 'data-services/types'

interface ResponseData {
  request_successful: boolean
  server_live: boolean
  pipelines_online: []
  error_code: number | null
  error_message: string | null
  prefix_exists: boolean
}

export const useTestProcessingServiceConnection = () => {
  const queryClient = useQueryClient()

  const { data, mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (params: { id: string; subdir?: string; regex?: string }) =>
      axios.get<ResponseData>(
        `${API_URL}/${API_ROUTES.PROCESSING_SERVICES}/${params.id}/status/`
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROCESSING_SERVICES])
    },
    onError: (error: AxiosError) => error,
  })

  let validationError = null
  if (error && error.response?.status === 400) {
    validationError = error.response?.data as APIValidationError
  }

  return {
    data: data?.data,
    testProcessingServiceConnection: mutateAsync,
    isLoading,
    isSuccess,
    error,
    validationError,
  }
}
