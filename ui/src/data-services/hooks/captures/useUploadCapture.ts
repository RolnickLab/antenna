import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

interface UploadCaptureFieldValues {
  projectId: string
  deploymentId: string
  file: File
}

export const useUploadCapture = (onSuccess?: (id: string) => void) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutate, isLoading, error, isSuccess } = useMutation({
    mutationFn: (fieldValues: UploadCaptureFieldValues) => {
      const data = new FormData()
      if (fieldValues.projectId) {
        data.append('project_id', fieldValues.projectId)
      }
      if (fieldValues.deploymentId) {
        data.append('deployment', fieldValues.deploymentId)
      }
      if (fieldValues.file) {
        data.append('image', fieldValues.file, fieldValues.file.name)
      } else if (fieldValues.file === null) {
        data.append('image', '')
      }

      return axios.post<{ source_image: { id: number } }>(
        `${API_URL}/${API_ROUTES.CAPTURES}/upload/`,
        data,
        {
          headers: {
            ...getAuthHeader(user),
            'Content-Type': 'multipart/form-data',
          },
        }
      )
    },
    onSuccess: ({ data }) => {
      queryClient.invalidateQueries([API_ROUTES.DEPLOYMENTS])
      onSuccess?.(`${data.source_image.id}`)
    },
  })

  return { uploadCapture: mutate, isLoading, error, isSuccess }
}
