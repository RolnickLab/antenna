import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { TaxonDetails } from 'nova-ui-kit'
import { useMemo, useRef, useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'
import { useUserInfo } from 'utils/user/userInfoContext'
import { Agree } from './agree/agree'
import { HumanIdentification } from './identification-card/human-identification'
import { MachinePrediction } from './identification-card/machine-prediction'
import styles from './occurrence-details.module.scss'
import { IdQuickActions } from './reject-id/id-quick-actions'
import { SuggestId } from './suggest-id/suggest-id'

export const TABS = {
  FIELDS: 'fields',
  IDENTIFICATION: 'identification',
}

export const OccurrenceDetails = ({
  occurrence,
  selectedTab,
  setSelectedTab,
}: {
  occurrence: Occurrence
  selectedTab?: string
  setSelectedTab: (selectedTab?: string) => void
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const suggestIdInputRef = useRef<HTMLInputElement>(null)
  const {
    user: { loggedIn },
  } = useUser()
  const { userInfo } = useUserInfo()
  const { state } = useLocation()
  const { projectId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [suggestIdOpen, setSuggestIdOpen] = useState<boolean>(
    state?.suggestIdOpen ?? false
  )
  const canUpdate = occurrence.userPermissions.includes(UserPermission.Update)

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
  ]

  return (
    <div className={styles.wrapper} ref={containerRef}>
      <Helmet>
        <meta name="og:image" content={occurrence.images[0]?.src} />
      </Helmet>
      <div className={styles.header}>
        <TaxonDetails
          taxon={occurrence.determinationTaxon}
          size="lg"
          withTooltips
        />
        <div className={styles.taxonActions}>
          <Tooltip
            content={
              occurrence.determinationVerified
                ? translate(STRING.VERIFIED_BY, {
                    name: occurrence.determinationVerifiedBy?.name,
                  })
                : translate(STRING.MACHINE_PREDICTION_SCORE, {
                    score: occurrence.determinationScore,
                  })
            }
          >
            <IdentificationStatus
              isVerified={occurrence.determinationVerified}
              score={occurrence.determinationScore}
            />
          </Tooltip>
          {canUpdate && (
            <>
              <Agree
                agreed={userInfo ? occurrence.userAgreed(userInfo?.id) : false}
                agreeWith={{
                  identificationId: occurrence.determinationIdentificationId,
                  predictionId: occurrence.determinationPredictionId,
                }}
                occurrenceId={occurrence.id}
                taxonId={occurrence.determinationTaxon.id}
              />
              <Button
                label={translate(STRING.SUGGEST_ID)}
                icon={IconType.RadixSearch}
                onClick={() => {
                  setSelectedTab(TABS.IDENTIFICATION)
                  setSuggestIdOpen(true)
                  suggestIdInputRef?.current?.focus()
                }}
              />
              <IdQuickActions
                containerRef={containerRef}
                occurrenceIds={[occurrence.id]}
                occurrenceTaxons={[occurrence.determinationTaxon]}
              />
            </>
          )}
          {!canUpdate && !loggedIn && (
            <Button
              label="Login to suggest ID"
              onClick={() =>
                navigate(APP_ROUTES.LOGIN, {
                  state: {
                    to: {
                      pathname: location.pathname,
                      search: location.search,
                    },
                  },
                })
              }
            />
          )}
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
                    {suggestIdOpen && (
                      <SuggestId
                        containerRef={containerRef}
                        inputRef={suggestIdInputRef}
                        occurrenceId={occurrence.id}
                        onCancel={() => setSuggestIdOpen(false)}
                      />
                    )}

                    {occurrence.humanIdentifications.map((i) => (
                      <HumanIdentification
                        key={i.id}
                        identification={i}
                        occurrence={occurrence}
                        user={i.user}
                        currentUser={userInfo}
                      />
                    ))}

                    {occurrence.machinePredictions.map((p) => (
                      <MachinePrediction
                        key={p.id}
                        identification={p}
                        occurrence={occurrence}
                        currentUser={userInfo}
                      />
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
