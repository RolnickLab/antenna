import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios, { AxiosResponse } from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { ServerTaxaList } from 'data-services/models/taxa-list'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useCopyTaxaList = (projectId: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      taxaListId,
      name,
      description,
    }: {
      taxaListId: string
      name?: string
      description?: string
    }): Promise<AxiosResponse<ServerTaxaList>> =>
      axios.post(
        `${API_URL}/${API_ROUTES.TAXA_LISTS}/${taxaListId}/copy/?project_id=${projectId}`,
        { name, description },
        { headers: getAuthHeader(user) }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.TAXA_LISTS])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { copyTaxaList: mutateAsync, error, isLoading, isSuccess, reset }
}
