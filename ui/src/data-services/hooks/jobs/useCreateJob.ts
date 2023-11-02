import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface JobFieldValues {
  delay?: number
  name: string
  projectId: string
  sourceImages?: string
}

const convertToServerFieldValues = (fieldValues: JobFieldValues) => ({
  delay: fieldValues.delay ?? 0,
  name: fieldValues.name,
  project: `http://api.dev.insectai.org/api/v2/projects/${fieldValues.projectId}/`,
  source_image_collection_id: fieldValues.sourceImages,
})

export const useCreateJob = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, error } = useMutation({
    mutationFn: (fieldValues: JobFieldValues) =>
      axios.post<{ id: number }>(
        `${API_URL}/${API_ROUTES.JOBS}/`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
      onSuccess?.(`${data.id}`)
    },
  })

  return { createJob: mutateAsync, isLoading, isSuccess, error }
}
