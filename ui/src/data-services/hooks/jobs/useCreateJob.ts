import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface JobFieldValues {
  delay?: number
  name: string
  projectId: string
  pipeline?: string
  sourceImage?: string
  sourceImages?: string
  startNow?: boolean
}

const convertToServerFieldValues = (fieldValues: JobFieldValues) => ({
  delay: fieldValues.delay ?? 0,
  name: fieldValues.name,
  project_id: fieldValues.projectId,
  job_type_key: 'ml',
  params: {
    config: {
      pipeline_id: fieldValues.pipeline || undefined,
      source_image_collection_id: fieldValues.sourceImages || undefined,
      source_image_single_id: fieldValues.sourceImage || undefined,
    },
  },
})

export const useCreateJob = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: JobFieldValues) =>
      axios.post<{ id: number; source_image_single?: { id: number } }>(
        `${API_URL}/${API_ROUTES.JOBS}/${
          fieldValues.startNow ? '?start_now' : ''
        }`,
        convertToServerFieldValues(fieldValues),
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.JOBS])
      queryClient.invalidateQueries([API_ROUTES.CAPTURES])
      onSuccess?.(`${data.id}`)
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { createJob: mutateAsync, isLoading, isSuccess, error }
}
