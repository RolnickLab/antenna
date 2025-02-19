import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import {
  TaxonInfo,
  TaxonInfoSize,
} from 'components/taxon/taxon-info/taxon-info'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()

  const blueprintItems: BlueprintItem[] = []

  const fields = [
    ...species.ranks.map(({ rank, name, id }) => ({
      label: rank,
      value: name,
      to: getAppRoute({
        to: APP_ROUTES.TAXON_DETAILS({
          projectId: projectId as string,
          taxonId: id,
        }),
        keepSearchParams: true,
      }),
    })),
    {
      label: translate(STRING.FIELD_LABEL_OCCURRENCES),
      value: 'View all',
      to: getAppRoute({
        to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        filters: { taxon: species.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_TRAINING_IMAGES),
      value: species.trainingImagesLabel,
      to: species.trainingImagesUrl,
    },
  ].filter((field) => field.value !== null)

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <TaxonInfo
          taxon={species}
          size={TaxonInfoSize.Large}
          getLink={(id: string) =>
            getAppRoute({
              to: APP_ROUTES.TAXON_DETAILS({
                projectId: projectId as string,
                taxonId: id,
              }),
            })
          }
        />
      </div>
      <div className={styles.content}>
        <div className={styles.column}>
          <div className={styles.info}>
            <div className={styles.fields}>
              <InfoBlock fields={fields} />
            </div>
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection items={blueprintItems} />
          </div>
        </div>
      </div>
    </div>
  )
}
