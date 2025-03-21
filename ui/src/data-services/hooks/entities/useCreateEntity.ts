import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'
import { EntityFieldValues } from './types'
import { convertToServerFieldValues } from './utils'

export const useCreateEntity = (collection: string, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: EntityFieldValues) =>
      axios.post(
        collection === API_ROUTES.EXPORTS
          ? `${API_URL}/${collection}/?project_id=${fieldValues.projectId}`
          : `${API_URL}/${collection}/`, // TODO: Skip this special handling when API is updated
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

  return { createEntity: mutateAsync, isLoading, isSuccess, error }
}
