import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { CopyLinkButton } from 'components/copy-link-button/copy-link-button'
import { TaxonDetails } from 'components/taxon-details/taxon-details'
import {
  FrameLabel,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { SearchIcon } from 'lucide-react'
import {
  BasicTooltip,
  Box,
  Button,
  CodeBlock,
  IdentificationScore,
  InfoBlockField,
  InfoBlockFieldValue,
  Tabs,
  buttonVariants,
} from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { useMemo, useRef, useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUser } from 'utils/user/userContext'
import { useUserInfo } from 'utils/user/userInfoContext'
import { Agree } from './agree/agree'
import { IdQuickActions } from './id-quick-actions/id-quick-actions'
import { GroupingConfirmation } from './identification-card/grouping-confirmation'
import { GroupingSummary } from './identification-card/grouping-summary'
import { HumanIdentification } from './identification-card/human-identification'
import { MachinePrediction } from './identification-card/machine-prediction'
import styles from './occurrence-details.module.scss'
import { StatusLabel } from './status-label/status-label'
import { SuggestId } from './suggest-id/suggest-id'
import { FrameActionDialogs } from './track/frame-action-dialogs'
import { FrameCaption } from './track/frame-caption'
import { FrameMenu } from './track/frame-menu'
import { GroupingActions } from './track/grouping-actions'
import { PendingFrameAction } from './track/types'

export const TABS = {
  FIELDS: 'fields',
  IDENTIFICATION: 'identification',
  RAW: 'raw',
}

const JumpToFrame = ({
  label,
  onClick,
  to,
}: {
  label: string
  onClick?: () => void
  to?: string
}) =>
  to ? (
    <Link
      className={cn(
        buttonVariants({ size: 'small', variant: 'ghost' }),
        'px-2'
      )}
      onClick={onClick}
      to={to}
    >
      <span>{label}</span>
    </Link>
  ) : null

export const OccurrenceDetails = ({
  occurrence,
  onNavigate,
  selectedTab,
  setSelectedTab,
}: {
  occurrence: Occurrence
  /** Called when a frame's link is followed, so a dialog around these details can close. */
  onNavigate?: () => void
  selectedTab?: string
  setSelectedTab: (selectedTab?: string) => void
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const {
    user: { loggedIn },
  } = useUser()
  const { userInfo } = useUserInfo()
  const { pathname, search } = useLocation()
  const { projectId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [suggestIdOpen, setSuggestIdOpen] = useState(false)
  const [pendingFrameAction, setPendingFrameAction] =
    useState<PendingFrameAction>()
  const canUpdate = occurrence.userPermissions.includes(UserPermission.Update)
  // Restructuring a grouping is gated on the occurrence delete right, confirming one
  // on either right — the same split the API makes. See #1272.
  const canRestructure = occurrence.userPermissions.includes(
    UserPermission.Delete
  )
  const canVerifyGrouping = canUpdate || canRestructure

  const sessionRoute = occurrence.sessionId
    ? APP_ROUTES.SESSION_DETAILS({
        projectId: projectId as string,
        sessionId: occurrence.sessionId,
      })
    : undefined

  const blueprintItems = useMemo(
    () =>
      occurrence.detections.length
        ? occurrence.detections
            .map((id) => occurrence.getDetectionInfo(id))
            .filter(
              (
                item
              ): item is BlueprintItem & {
                captureId: string
                frameLabel: FrameLabel
                hasVector: boolean | undefined
              } => !!item
            )
            .map((item) => {
              if (!sessionRoute) {
                return { ...item, to: undefined }
              }

              // On the session page itself, keep the other selected occurrences and
              // only move the capture.
              if (pathname === sessionRoute) {
                const params = new URLSearchParams(search)
                if (!params.getAll('occurrence').includes(occurrence.id)) {
                  params.append('occurrence', occurrence.id)
                }
                params.set('capture', item.captureId)

                return { ...item, to: `${sessionRoute}?${params}` }
              }

              return {
                ...item,
                to: getAppRoute({
                  to: sessionRoute,
                  filters: {
                    occurrence: occurrence.id,
                    capture: item.captureId,
                  },
                }),
              }
            })
        : [],
    [occurrence, pathname, search, sessionRoute]
  )

  // The strip runs newest first, so the track's earliest frame is its last row.
  const newestFrame = blueprintItems[0]
  const earliestFrame = blueprintItems[blueprintItems.length - 1]

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
      value: occurrence.deploymentLabel,
      to: occurrence.deploymentId
        ? APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId: projectId as string,
            deploymentId: occurrence.deploymentId,
          })
        : undefined,
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
          {occurrence.determinationScore !== undefined ? (
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
          ) : null}
          {canUpdate && (
            <>
              {occurrence.determinationTaxon ? (
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
              ) : null}
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
                occurrenceIds={[occurrence.id]}
                occurrenceTaxa={
                  occurrence.determinationTaxon
                    ? [occurrence.determinationTaxon]
                    : []
                }
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
                    {fields.map((field, index) => (
                      <InfoBlockField key={index} label={field.label}>
                        <InfoBlockFieldValue
                          value={field.value}
                          to={field.to}
                        />
                      </InfoBlockField>
                    ))}
                    <InfoBlockField
                      label={translate(STRING.FIELD_LABEL_OCCURRENCE_NUMBER)}
                    >
                      <div className="flex items-center gap-1">
                        <InfoBlockFieldValue value={occurrence.id} />
                        <CopyLinkButton value={window.location.href} />
                      </div>
                    </InfoBlockField>
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

                    {occurrence.groupingVerifiedAt ? (
                      <GroupingConfirmation occurrence={occurrence} />
                    ) : null}

                    {occurrence.groupingSummary ? (
                      <GroupingSummary
                        frameNames={occurrence.frameNames}
                        summary={occurrence.groupingSummary}
                      />
                    ) : null}

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
            {(canRestructure || canVerifyGrouping) && (
              <GroupingActions
                canRestructure={canRestructure}
                canVerify={canVerifyGrouping}
                occurrence={occurrence}
              />
            )}
            <BlueprintCollection
              filmStrip
              showLicenseInfo={blueprintItems.length > 0}
            >
              {blueprintItems.length ? (
                <div className="flex flex-wrap items-center justify-between gap-1 pb-2">
                  <span className="body-small text-muted-foreground">
                    {blueprintItems.length === 1
                      ? translate(STRING.TRACK_FRAMES_ONE)
                      : translate(STRING.TRACK_FRAMES_COUNT, {
                          count: blueprintItems.length,
                        })}
                  </span>
                  <div className="flex flex-wrap items-center gap-1">
                    {blueprintItems.length === 1 ? (
                      <JumpToFrame
                        label={translate(STRING.TRACK_JUMP_ONLY_FRAME)}
                        onClick={onNavigate}
                        to={newestFrame.to}
                      />
                    ) : (
                      <>
                        <JumpToFrame
                          label={translate(STRING.TRACK_JUMP_FIRST_FRAME)}
                          onClick={onNavigate}
                          to={earliestFrame.to}
                        />
                        <JumpToFrame
                          label={translate(STRING.TRACK_JUMP_LAST_FRAME)}
                          onClick={onNavigate}
                          to={newestFrame.to}
                        />
                      </>
                    )}
                  </div>
                </div>
              ) : null}
              {blueprintItems.map((item, index) => (
                <BlueprintItem
                  actions={
                    canRestructure ? (
                      <FrameMenu
                        isFirstInTime={index === blueprintItems.length - 1}
                        isOnlyFrame={blueprintItems.length < 2}
                        onAction={(action) =>
                          setPendingFrameAction({
                            action,
                            captureId: item.captureId,
                            detectionId: item.id,
                            movedBySplit: index + 1,
                            timeLabel: item.timeLabel,
                            total: blueprintItems.length,
                          })
                        }
                      />
                    ) : undefined
                  }
                  caption={
                    <FrameCaption
                      detectionId={item.id}
                      hasVector={item.hasVector}
                      label={item.frameLabel}
                      timeLabel={item.timeLabel}
                    />
                  }
                  key={item.id}
                  item={item}
                  onLinkClick={onNavigate}
                />
              ))}
            </BlueprintCollection>
            <FrameActionDialogs
              occurrence={occurrence}
              onClose={() => setPendingFrameAction(undefined)}
              pending={pendingFrameAction}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
