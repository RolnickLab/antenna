import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { IdentificationSummary } from 'design-system/components/identification/identification-summary/identification-summary'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'

export const OccurrenceDetails = ({
  occurrence,
}: {
  occurrence: Occurrence
}) => {
  const { projectId } = useParams()
  console.log('occurrence: ', occurrence)

  const blueprintItems = useMemo(
    () =>
      occurrence.detections.length
        ? occurrence.detections
            .map((id) => occurrence.getDetectionInfo(id))
            .filter(
              (item): item is BlueprintItem & { captureId: string } => !!item
            )
            .map((item) => ({
              ...item,
              to: getAppRoute({
                to: APP_ROUTES.SESSION_DETAILS({
                  projectId: projectId as string,
                  sessionId: occurrence.sessionId,
                }),
                filters: {
                  occurrence: occurrence.id,
                  capture: item.captureId,
                },
              }),
            }))
        : [],
    [occurrence]
  )

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
      value: occurrence.deploymentLabel,
      to: APP_ROUTES.DEPLOYMENTS({ projectId: projectId as string }),
    },
    {
      label: translate(STRING.FIELD_LABEL_SESSION),
      value: occurrence.sessionLabel,
      to: getAppRoute({
        to: APP_ROUTES.SESSION_DETAILS({
          projectId: projectId as string,
          sessionId: occurrence.sessionId,
        }),
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
          to={APP_ROUTES.SPECIES_DETAILS({
            projectId: projectId as string,
            speciesId: occurrence.determinationId,
          })}
        >
          <span className={styles.title}>{occurrence.determinationLabel}</span>
        </Link>
      </div>
      <div className={styles.content}>
        <div className={styles.column}>
          <div className={styles.info}>
            <div className={styles.fields}>
              <Tabs.Root defaultValue="fields">
                <Tabs.List>
                  <Tabs.Trigger
                    value="fields"
                    label={translate(STRING.TAB_ITEM_FIELDS)}
                  />
                  <Tabs.Trigger
                    value="identification"
                    label={translate(STRING.TAB_ITEM_IDENTIFICATION)}
                  />
                </Tabs.List>
                <Tabs.Content value="fields">
                  <InfoBlock fields={fields} />
                </Tabs.Content>
                <Tabs.Content value="identification">
                  <div className={styles.identifications}>
                    {occurrence.identifications.map((i) => (
                      <IdentificationSummary
                        identification={{
                          id: `${i.id}`,
                          overridden: false,
                          title: i.taxon.name,
                        }}
                        ranks={[
                          {
                            id: 'rank-1',
                            title: 'Rank 1',
                          },
                          {
                            id: 'rank-2',
                            title: 'Rank 2',
                          },
                          {
                            id: 'rank-3',
                            title: 'Rank 3',
                          },
                        ]}
                        user={{
                          username: i.user.name,
                          profileImage: i.user.image,
                        }}
                      />
                    ))}
                    <IdentificationSummary
                      identification={{
                        id: occurrence.determinationId,
                        overridden: occurrence.identifications.length > 0,
                        title: occurrence.determinationLabel,
                      }}
                      ranks={[
                        {
                          id: 'rank-1',
                          title: 'Rank 1',
                        },
                        {
                          id: 'rank-2',
                          title: 'Rank 2',
                        },
                        {
                          id: 'rank-3',
                          title: 'Rank 3',
                        },
                      ]}
                    />
                  </div>
                </Tabs.Content>
              </Tabs.Root>
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
