import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import {
  TaxonInfo,
  TaxonInfoSize,
} from 'components/taxon/taxon-info/taxon-info'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { IdentificationSummary } from 'design-system/components/identification/identification-summary/identification-summary'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { useMemo, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './occurrence-details.module.scss'
import { SuggestId } from './suggest-id/suggest-id'

export const TABS = {
  FIELDS: 'fields',
  IDENTIFICATION: 'identification',
}

export const OccurrenceDetails = ({
  occurrence,
}: {
  occurrence: Occurrence
}) => {
  const { state } = useLocation()
  const { projectId } = useParams()
  const [selectedTab, setSelectedTab] = useState<string | undefined>(
    state?.defaultTab ?? TABS.FIELDS
  )
  const [suggestIdOpen, setSuggestIdOpen] = useState<boolean>(
    state?.suggestIdOpen ?? false
  )

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

  const getTaxonLink = (id: string) =>
    getAppRoute({
      to: APP_ROUTES.SPECIES_DETAILS({
        projectId: projectId as string,
        speciesId: id,
      }),
    })

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <TaxonInfo
          taxon={occurrence.determinationTaxon}
          size={TaxonInfoSize.Large}
          getLink={getTaxonLink}
        />
        <div className={styles.taxonActions}>
          <IdentificationStatus
            isVerified={occurrence.determinationVerified}
            score={occurrence.determinationScore}
          />
          <Button
            label="Suggest ID"
            theme={ButtonTheme.Default}
            disabled={selectedTab === TABS.IDENTIFICATION && suggestIdOpen}
            onClick={() => {
              setSelectedTab(TABS.IDENTIFICATION)
              setSuggestIdOpen(true)
            }}
          />
        </div>
      </div>
      <div className={styles.content}>
        <div className={styles.infoWrapper}>
          <div className={styles.infoContainer}>
            <div className={styles.fields}>
              <Tabs.Root value={selectedTab} onValueChange={setSelectedTab}>
                <Tabs.List>
                  <Tabs.Trigger
                    value={TABS.FIELDS}
                    label={translate(STRING.TAB_ITEM_FIELDS)}
                  />
                  <Tabs.Trigger
                    value={TABS.IDENTIFICATION}
                    label={translate(STRING.TAB_ITEM_IDENTIFICATION)}
                  />
                </Tabs.List>
                <Tabs.Content value={TABS.FIELDS}>
                  <InfoBlock fields={fields} />
                </Tabs.Content>
                <Tabs.Content value={TABS.IDENTIFICATION}>
                  <div className={styles.identifications}>
                    <SuggestId
                      occurrenceId={occurrence.id}
                      open={suggestIdOpen}
                      onOpenChange={setSuggestIdOpen}
                    />

                    {occurrence.humanIdentifications.map((i) => (
                      <div key={i.id} className={styles.identification}>
                        <IdentificationSummary user={i.user}>
                          <TaxonInfo
                            overridden={i.overridden}
                            taxon={i.taxon}
                            getLink={getTaxonLink}
                          />
                        </IdentificationSummary>
                      </div>
                    ))}

                    {occurrence.machinePredictions.map((p) => (
                      <div key={p.id} className={styles.identification}>
                        <IdentificationSummary>
                          <TaxonInfo
                            overridden={p.overridden}
                            taxon={p.taxon}
                            getLink={getTaxonLink}
                          />
                        </IdentificationSummary>
                        <IdentificationStatus score={p.score} />
                      </div>
                    ))}
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
