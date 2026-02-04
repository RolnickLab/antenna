import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useRemoveTaxaListTaxon = (projectId: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: ({
      taxaListId,
      taxonId,
    }: {
      taxaListId: string
      taxonId: string
    }) =>
      axios.delete(
        `${API_URL}/${API_ROUTES.TAXA_LISTS}/${taxaListId}/taxa/${taxonId}/?project_id=${projectId}`,
        {
          headers: getAuthHeader(user),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.TAXA_LISTS])
      queryClient.invalidateQueries([API_ROUTES.SPECIES])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { removeTaxaListTaxon: mutateAsync, isLoading, error, isSuccess }
}
