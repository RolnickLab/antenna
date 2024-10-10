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
import { useMemo } from 'react'
import { Helmet } from 'react-helmet-async'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()

  const image = useMemo(() => {
    if (species.occurrences.length) {
      const occurrenceInfo = species.getOccurrenceInfo(species.occurrences[0])
      return occurrenceInfo?.image.src
    }
  }, [species])

  const blueprintItems = useMemo(
    () =>
      species.occurrences.length
        ? species.occurrences
            .map((id) => species.getOccurrenceInfo(id))
            .filter((item): item is BlueprintItem => !!item)
            .map((item) => ({
              ...item,
              to: APP_ROUTES.OCCURRENCE_DETAILS({
                projectId: projectId as string,
                occurrenceId: item.id,
              }),
            }))
        : [],
    [species]
  )

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DETECTIONS),
      value: species.numDetections,
    },
    {
      label: translate(STRING.FIELD_LABEL_OCCURRENCES),
      value: species.numOccurrences || 'View all',
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
      <Helmet>
        <meta name="og:image" content={image} />
      </Helmet>
      <div className={styles.header}>
        <TaxonInfo
          taxon={species}
          size={TaxonInfoSize.Large}
          getLink={(id: string) =>
            getAppRoute({
              to: APP_ROUTES.SPECIES_DETAILS({
                projectId: projectId as string,
                speciesId: id,
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
