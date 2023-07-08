import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'

export const OccurrenceDetails = ({
  occurrence,
}: {
  occurrence: Occurrence
}) => {
  const blueprintItems = useMemo(
    () =>
      occurrence.detections.length
        ? occurrence.detections
            .map((id) => occurrence.getDetectionInfo(id))
            .filter((item): item is BlueprintItem => !!item)
        : [],
    [occurrence]
  )

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
      value: occurrence.deploymentLabel,
      to: getRoute({
        collection: 'deployments',
        itemId: occurrence.deploymentId,
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_SESSION),
      value: occurrence.sessionLabel,
      to: getRoute({
        collection: 'sessions',
        itemId: occurrence.sessionId,
        filters: { occurrence: occurrence.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_DATE),
      value: occurrence.dateLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_TIME),
      value: occurrence.timeLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_DURATION),
      value: occurrence.durationLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_DETECTIONS),
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
            <div className={styles.fields}>
              {/* TODO: Replace with tabs below when classifications are in place */}
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

/* eslint-disable @typescript-eslint/no-unused-vars */
const InfoTabs = () => (
  <Tabs.Root defaultValue="fields">
    <Tabs.List>
      <Tabs.Trigger value="fields" label={translate(STRING.TAB_ITEM_FIELDS)} />
      <Tabs.Trigger
        value="classification"
        label={translate(STRING.TAB_ITEM_CLASSIFICATION)}
      />
    </Tabs.List>
    <Tabs.Content value="fields">
      <div className={styles.fields}>
        <InfoBlock fields={[]} />
      </div>
    </Tabs.Content>
    <Tabs.Content value="classification">
      <div className={styles.fields}>
        <InfoBlock fields={[]} />
      </div>
    </Tabs.Content>
  </Tabs.Root>
)
