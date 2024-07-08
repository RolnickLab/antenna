import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios, { AxiosError } from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { APIValidationError } from 'data-services/types'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useSyncStorage = () => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (params: {
      id: string
      subDir?: string
      regexFilter?: string
    }) =>
      axios.post<{ full_uri: string }>(
        `${API_URL}/${API_ROUTES.STORAGE}/${params.id}/test/`,
        {
          subdir: params.subDir,
          regexFilter: params.regexFilter,
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
    syncStorage: mutateAsync,
    isLoading,
    isSuccess,
    error,
    validationError,
  }
}
