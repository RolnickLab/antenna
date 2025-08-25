import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, SUCCESS_TIMEOUT } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

const convertToServerFieldValues = (fieldValues: any) => ({
  settings: {
    session_time_gap_seconds: fieldValues.sessionTimeGapSeconds,
    default_filters_score_threshold: fieldValues.scoreThreshold,
    default_filters_include_taxa_ids: fieldValues.includeTaxa.map(
      (taxon: any) => taxon.id
    ),
    default_filters_exclude_taxa_ids: fieldValues.excludeTaxa.map(
      (taxon: any) => taxon.id
    ),
  },
})

export const useUpdateProjectSettings = (id: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  const { mutateAsync, isLoading, isSuccess, reset, error } = useMutation({
    mutationFn: (fieldValues: any) =>
      axios.patch(
        `${API_URL}/${API_ROUTES.PROJECTS}/${id}/`,
        convertToServerFieldValues(fieldValues),
        {
          headers: {
            ...getAuthHeader(user),
          },
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries([API_ROUTES.PROJECTS, id])
      setTimeout(reset, SUCCESS_TIMEOUT)
    },
  })

  return { updateProjectSettings: mutateAsync, isLoading, isSuccess, error }
}
