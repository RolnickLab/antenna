import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'
import { EntityFieldValues } from './types'
import { convertToServerFieldValues } from './utils'

const SUCCESS_TIMEOUT = 1000 // Reset success after 1 second

export const useUpdateEntity = (
  id: string,
  collection: string,
  onSuccess?: () => void
) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: EntityFieldValues) =>
      axios.patch(
        `${API_URL}/${collection}/${id}/`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([collection])
      onSuccess?.()
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { updateEntity: mutateAsync, isLoading, error, isSuccess }
}
