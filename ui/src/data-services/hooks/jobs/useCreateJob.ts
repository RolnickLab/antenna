import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { JobStatus } from 'data-services/models/job'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface JobFieldValues {
  name: string
  projectId: string
  status: JobStatus
}

const convertToServerFieldValues = (fieldValues: JobFieldValues) => ({
  name: fieldValues.name,
  project_id: fieldValues.projectId,
  status: fieldValues.status,
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
