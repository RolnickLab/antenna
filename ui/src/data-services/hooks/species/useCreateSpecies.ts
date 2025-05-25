import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { booleanToString } from 'components/filtering/utils'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCreateSpecies = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: {
      projectId: string
      name: string
      parentId: string
      unknownSpecies: boolean
    }) => {
      const data = new FormData()
      data.append('project_id', fieldValues.projectId)
      data.append('name', fieldValues.name)
      data.append('parent_id', fieldValues.parentId)
      data.append(
        'unknown_species',
        booleanToString(fieldValues.unknownSpecies)
      )

      return axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.SPECIES}/`,
        data,
        {
          headers: {
            ...getAuthHeader(user),
            'Content-Type': 'multipart/form-data',
          },
        }
      )
    },
    onSuccess: (resp) => {
      queryClient.invalidateQueries([API_ROUTES.SPECIES])
      onSuccess?.(`${resp.data.id}`)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createSpecies: mutateAsync, isLoading, isSuccess, error }
}
