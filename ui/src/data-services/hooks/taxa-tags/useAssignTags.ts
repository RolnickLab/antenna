import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { Tag } from 'data-services/models/species'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAssignTags = (id: string, onSuccess?: () => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutate, isLoading, error, isSuccess, reset } = useMutation({
    mutationFn: ({ projectId, tags }: { projectId: string; tags: Tag[] }) =>
      axios.post(
        `${API_URL}/${API_ROUTES.SPECIES}/${id}/assign_tags/?project_id=${projectId}`,
        {
          tag_ids: tags.map((tag) => tag.id),
        },
        {
          headers: {
            ...getAuthHeader(user),
          },
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.SPECIES])
      queryClient.invalidateQueries([API_ROUTES.SPECIES, id])
      onSuccess?.()
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { assignTags: mutate, isLoading, error, isSuccess }
}
