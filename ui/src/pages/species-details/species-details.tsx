import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { useMemo } from 'react'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const blueprintItems = useMemo(
    () =>
      species.occurrences.length
        ? species?.occurrences
            .map((id) => species.getOccurrenceInfo(id))
            .filter((item): item is BlueprintItem => !!item)
            .map((item) => ({
              ...item,
              to: getRoute({ collection: 'occurrences', itemId: item.id }),
            }))
        : [],
    [species]
  )

  const fields = [
    {
      label: translate(STRING.TABLE_COLUMN_DETECTIONS),
      value: species.numDetections,
    },
    {
      label: translate(STRING.TABLE_COLUMN_OCCURRENCES),
      value: species.numOccurrences,
      to: getRoute({
        collection: 'occurrences',
        filters: { determination: species.id },
      }),
    },
    {
      label: 'Training images',
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
