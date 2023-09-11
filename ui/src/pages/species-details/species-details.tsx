import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()

  const blueprintItems = useMemo(
    () =>
      species.occurrences.length
        ? species?.occurrences
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
      value: species.numOccurrences,
      to: getAppRoute({
        to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        filters: { determination: species.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_TRAINING_IMAGES),
      value: species.trainingImagesLabel,
      to: species.trainingImagesUrl,
    },
  ]

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <span className={styles.title}>{species.name}</span>
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
