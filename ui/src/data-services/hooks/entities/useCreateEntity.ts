import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'
import { EntityFieldValues } from './types'
import { convertToServerFieldValues } from './utils'

export const useCreateEntity = (
  collection: string,
  onSuccess?: (created: { id: number }) => void
) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: EntityFieldValues) =>
      axios.post<{ id: number }>(
        `${API_URL}/${collection}/?project_id=${fieldValues.projectId}`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: (response) => {
      queryClient.invalidateQueries([collection])
      onSuccess?.(response.data)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createEntity: mutateAsync, isLoading, isSuccess, error }
}
