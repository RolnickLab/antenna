import { useOccurrenceDetails } from 'data-services/hooks/useOccurrenceDetails'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Popover from 'design-system/components/popover/popover'
import * as Tabs from 'design-system/components/tabs/tabs'
import { STRING, translate } from 'utils/language'
import { BlueprintDetections } from './blueprint-detections/blueprint-detections'
import styles from './occurrence-details.module.scss'
import { TaxonomyInfo } from './taxonomy-info/taxonomy-info'

export const OccurrenceDetails = ({ id }: { id: string }) => {
  const { occurrence } = useOccurrenceDetails(id)

  if (!occurrence) {
    return null
  }

  const fields = [
    {
      label: translate(STRING.DETAILS_LABEL_DEPLOYMENT),
      value: occurrence.deploymentLabel,
      to: `/deployments/${occurrence.deploymentId}`,
    },
    {
      label: translate(STRING.DETAILS_LABEL_SESSION),
      value: occurrence.sessionLabel,
      to: `/sessions/${occurrence.sessionId}`,
    },
  ]

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <Popover.Root>
          <Popover.Trigger asChild={false}>
            <span className={styles.title}>
              {occurrence.determinationLabel}
            </span>
          </Popover.Trigger>
          <Popover.Content
            ariaCloselabel={translate(STRING.CLOSE)}
            align="start"
            side="bottom"
          >
            <TaxonomyInfo />
          </Popover.Content>
        </Popover.Root>
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
            <BlueprintDetections occurrence={occurrence} />
          </div>
        </div>
      </div>
    </div>
  )
}
