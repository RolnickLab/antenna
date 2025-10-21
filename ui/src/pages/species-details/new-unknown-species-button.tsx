import { useCreateSpecies } from 'data-services/hooks/species/useCreateSpecies'
import { Loader2Icon, PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const NewUnknownSpeciesButton = () => {
  const navigate = useNavigate()
  const { projectId } = useParams()

  const { createSpecies, isLoading } = useCreateSpecies((id) => {
    navigate(
      getAppRoute({
        to: APP_ROUTES.TAXON_DETAILS({
          projectId: projectId as string,
          taxonId: id,
        }),
        keepSearchParams: true,
      })
    )
  })

  return (
    <Button
      onClick={() =>
        createSpecies({
          projectId: projectId as string,
          name: `Cluster (${new Date().toISOString()})`,
          parentId: '2361', // Cluster
          unknownSpecies: true,
        })
      }
      size="small"
      variant="outline"
    >
      {isLoading ? (
        <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
      ) : (
        <PlusIcon className="w-4 h-4" />
      )}
      <span>{translate(STRING.ENTITY_CREATE, { type: 'cluster' })}</span>
    </Button>
  )
}
