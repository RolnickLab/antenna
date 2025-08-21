import { useCreateSpecies } from 'data-services/hooks/species/useCreateSpecies'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
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
      icon={IconType.Plus}
      label={translate(STRING.ENTITY_CREATE, { type: 'cluster' })}
      loading={isLoading}
      onClick={() =>
        createSpecies({
          projectId: projectId as string,
          name: `Cluster (${new Date().toISOString()})`,
          parentId: '2361', // Cluster
          unknownSpecies: true,
        })
      }
    />
  )
}
