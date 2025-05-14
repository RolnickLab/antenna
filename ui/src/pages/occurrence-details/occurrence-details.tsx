import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { OODScore } from 'components/ood-score'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import {
  InfoBlockField,
  InfoBlockFieldValue,
} from 'design-system/components/info-block/info-block'
import * as Tabs from 'design-system/components/tabs/tabs'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { SearchIcon } from 'lucide-react'
import {
  Box,
  Button,
  CodeBlock,
  IdentificationScore,
  TaxonDetails,
} from 'nova-ui-kit'
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
import { StatusLabel } from './status-label/status-label'
import { SuggestId } from './suggest-id/suggest-id'

export const TABS = {
  FIELDS: 'fields',
  IDENTIFICATION: 'identification',
  RAW: 'raw',
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
  const {
    user: { loggedIn },
  } = useUser()
  const { userInfo } = useUserInfo()
  const { pathname } = useLocation()
  const { projectId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [suggestIdOpen, setSuggestIdOpen] = useState(false)
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
              to:
                !occurrence.sessionId ||
                pathname.includes(
                  APP_ROUTES.SESSIONS({ projectId: projectId as string })
                )
                  ? undefined
                  : getAppRoute({
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
      to:
        !occurrence.sessionId ||
        pathname.includes(
          APP_ROUTES.SESSIONS({ projectId: projectId as string })
        )
          ? undefined
          : getAppRoute({
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
  ]

  return (
    <div className={styles.wrapper} ref={containerRef}>
      <Helmet>
        <meta name="og:image" content={occurrence.images[0]?.src} />
      </Helmet>
      <div className={styles.header}>
        <TaxonDetails
          onTaxonClick={(id) =>
            navigate(
              getAppRoute({
                to: APP_ROUTES.TAXON_DETAILS({
                  projectId: projectId as string,
                  taxonId: id,
                }),
              })
            )
          }
          size="lg"
          taxon={occurrence.determinationTaxon}
        />
        <div className={styles.taxonActions}>
          <BasicTooltip
            content={
              occurrence.determinationVerified
                ? translate(STRING.VERIFIED_BY, {
                    name: occurrence.determinationVerifiedBy?.name,
                  })
                : translate(STRING.MACHINE_PREDICTION_SCORE, {
                    score: `${occurrence.determinationScore}`,
                  })
            }
          >
            <IdentificationScore
              confirmed={occurrence.determinationVerified}
              confidenceScore={occurrence.determinationScore}
            />
          </BasicTooltip>
          {canUpdate && (
            <>
              <Agree
                agreed={userInfo ? occurrence.userAgreed(userInfo.id) : false}
                agreeWith={{
                  identificationId: occurrence.determinationIdentificationId,
                  predictionId: occurrence.determinationPredictionId,
                }}
                applied
                occurrenceId={occurrence.id}
                taxonId={occurrence.determinationTaxon.id}
              />
              <Button
                onClick={() => {
                  setSelectedTab(TABS.IDENTIFICATION)
                  setSuggestIdOpen(true)
                }}
                size="small"
                variant="outline"
              >
                <SearchIcon className="w-4 h-4" />
                <span>{translate(STRING.SUGGEST_ID)}</span>
              </Button>
              <IdQuickActions
                containerRef={containerRef}
                occurrenceIds={[occurrence.id]}
                occurrenceTaxons={[occurrence.determinationTaxon]}
              />
            </>
          )}
          {!canUpdate && !loggedIn && (
            <Button
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
              size="small"
              variant="outline"
            >
              Login to suggest ID
            </Button>
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
                  <Tabs.Trigger value={TABS.RAW} label="Raw" />
                </Tabs.List>
                <Tabs.Content value={TABS.FIELDS}>
                  <div className="grid gap-6">
                    <InfoBlockField
                      label={translate(STRING.FIELD_LABEL_OOD_SCORE)}
                    >
                      <div>
                        <OODScore occurrence={occurrence} />
                      </div>
                    </InfoBlockField>
                    {fields.map((field, index) => (
                      <InfoBlockField key={index} label={field.label}>
                        <InfoBlockFieldValue
                          value={field.value}
                          to={field.to}
                        />
                      </InfoBlockField>
                    ))}
                  </div>
                </Tabs.Content>
                <Tabs.Content value={TABS.IDENTIFICATION}>
                  <div className={styles.identifications}>
                    {suggestIdOpen && (
                      <Box className="p-0 relative">
                        <StatusLabel label={translate(STRING.NEW_ID)} />
                        <SuggestId
                          occurrenceIds={[occurrence.id]}
                          onCancel={() => setSuggestIdOpen(false)}
                        />
                      </Box>
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
                <Tabs.Content value={TABS.RAW}>
                  <div className="flex flex-col gap-4">
                    <CodeBlock
                      className="flex items-center"
                      externalLink={occurrence.endpointURL}
                      snippet={`GET ${occurrence.endpointURL}`}
                    />
                    <CodeBlock snippet={occurrence.rawData} />
                  </div>
                </Tabs.Content>
              </Tabs.Root>
            </div>
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection showLicenseInfo={blueprintItems.length > 0}>
              {blueprintItems.map((item) => (
                <BlueprintItem key={item.id} item={item} />
              ))}
            </BlueprintCollection>
          </div>
        </div>
      </div>
    </div>
  )
}
