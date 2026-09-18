import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'
import { EntityFieldValues } from './types'
import { convertToServerFieldValues } from './utils'

// The created entity, as the server returns it. Callers read the fields their own
// collection defines; `is_async` is how a processing service reports its mode.
export type CreatedEntity = { id?: number; is_async?: boolean }

// Most collections return the created entity itself. Processing services wrap it,
// returning the connection status alongside it, so the entity lives one level down.
type CreateEntityResponse = CreatedEntity & { instance?: CreatedEntity }

const getCreatedEntity = (data: CreateEntityResponse): CreatedEntity =>
  data.instance ?? data

export const useCreateEntity = (
  collection: string,
  onSuccess?: (created: CreatedEntity) => void
) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: EntityFieldValues) =>
      axios.post<CreateEntityResponse>(
        `${API_URL}/${collection}/?project_id=${fieldValues.projectId}`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: (response) => {
      queryClient.invalidateQueries([collection])
      onSuccess?.(getCreatedEntity(response.data))
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createEntity: mutateAsync, isLoading, isSuccess, error }
}
