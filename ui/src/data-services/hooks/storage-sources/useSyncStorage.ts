import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios, { AxiosError } from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { APIValidationError } from 'data-services/types'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface ResponseData {
  connection_successful: boolean
  error_code: number | null
  error_message: string | null
  files_checked: number
  first_file_found: string | null
  full_uri: string
  latency: number
  prefix_exists: boolean
  total_time: number
}

export const useSyncStorage = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { data, mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (params: { id: string; subdir?: string; regex?: string }) =>
      axios.post<ResponseData>(
        `${API_URL}/${API_ROUTES.STORAGE}/${params.id}/test/`,
        {
          ...(params.subdir ? { subdir: params.subdir } : {}),
          ...(params.regex ? { regex_filter: params.regex } : {}),
        },
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.STORAGE])
    },
    onError: (error: AxiosError) => error,
  })

  let validationError = null
  if (error && error.response?.status === 400) {
    validationError = error.response?.data as APIValidationError
  }

  return {
    data: data?.data,
    syncStorage: mutateAsync,
    isLoading,
    isSuccess,
    error,
    validationError,
  }
}
