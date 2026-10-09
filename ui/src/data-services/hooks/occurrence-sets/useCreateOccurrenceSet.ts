import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface OccurrenceSetFieldValues {
  name: string
  description?: string
  projectId: string
  occurrenceIds: string[]
}

const convertToServerFieldValues = (fieldValues: OccurrenceSetFieldValues) => ({
  name: fieldValues.name,
  description: fieldValues.description ?? '',
  project_id: fieldValues.projectId,
  occurrence_ids: fieldValues.occurrenceIds.map((id) => Number(id)),
})

export const useCreateOccurrenceSet = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: OccurrenceSetFieldValues) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.OCCURRENCE_SETS}/`,
        convertToServerFieldValues(fieldValues),
        { headers: getAuthHeader(user) }
      ),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.OCCURRENCE_SETS])
      queryClient.invalidateQueries([API_ROUTES.OCCURRENCE_SET_CHOICES])
      onSuccess?.(`${data.id}`)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createOccurrenceSet: mutateAsync, isLoading, isSuccess, error }
}
