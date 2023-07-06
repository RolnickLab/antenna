import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { useOccurrenceDetails } from 'data-services/hooks/useOccurrenceDetails'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'

export const OccurrenceDetails = ({ id }: { id: string }) => {
  const { occurrence } = useOccurrenceDetails(id)

  const blueprintItems = useMemo(
    () =>
      occurrence?.detections.length
        ? occurrence.detections
            .map((id) => occurrence.getDetectionInfo(id))
            .filter((item): item is BlueprintItem => !!item)
        : [],
    [occurrence]
  )

  if (!occurrence) {
    return null
  }

  const fields = [
    {
      label: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
      value: occurrence.deploymentLabel,
      to: getRoute({
        collection: 'deployments',
        itemId: occurrence.deploymentId,
      }),
    },
    {
      label: translate(STRING.TABLE_COLUMN_SESSION),
      value: occurrence.sessionLabel,
      to: getRoute({ collection: 'sessions', itemId: occurrence.sessionId }),
    },
    {
      label: translate(STRING.TABLE_COLUMN_DATE),
      value: occurrence.dateLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_TIME),
      value: occurrence.timeLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_DURATION),
      value: occurrence.durationLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_DETECTIONS),
      value: occurrence.numDetections,
    },
  ]

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <Link
          to={getRoute({
            collection: 'species',
            itemId: occurrence.determinationId,
          })}
        >
          <span className={styles.title}>{occurrence.determinationLabel}</span>
        </Link>
      </div>
      <div className={styles.content}>
        <div className={styles.column}>
          <div className={styles.info}>
            <Tabs.Root defaultValue="fields">
              <Tabs.List>
                <Tabs.Trigger
                  value="fields"
                  label={translate(STRING.TAB_ITEM_FIELDS)}
                />
                <Tabs.Trigger
                  value="classification"
                  label={translate(STRING.TAB_ITEM_CLASSIFICATION)}
                />
              </Tabs.List>
              <Tabs.Content value="fields">
                <div className={styles.fields}>
                  <InfoBlock fields={fields} />
                </div>
              </Tabs.Content>
              <Tabs.Content value="classification">
                <div className={styles.fields}>
                  <InfoBlock fields={[]} />
                </div>
              </Tabs.Content>
            </Tabs.Root>
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
