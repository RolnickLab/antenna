import { ErrorState } from 'components/error-state/error-state'
import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { useSessionTimeline } from 'data-services/hooks/sessions/useSessionTimeline'
import { SessionDetails } from 'data-services/models/session-details'
import { ExternalLinkIcon } from 'lucide-react'
import {
  BasicTooltip,
  Box,
  buttonVariants,
  LoadingSpinner,
  PageHeader,
  Tabs,
} from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { useContext, useEffect, useRef, useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { useParams } from 'react-router-dom'
import { ReactZoomPanPinchRef } from 'react-zoom-pan-pinch'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { useUser } from 'utils/user/userContext'
import { ActivityPlot } from './activity-plot/lazy-activity-plot'
import { CaptureInfo } from './capture-info'
import { CaptureNavigation } from './capture-navigation'
import { Capture } from './capture/capture'
import { useActiveCaptureId } from './hooks/useActiveCapture'
import { useActiveOccurrences } from './hooks/useActiveOccurrences'
import { Process } from './process/process'
import { SessionInfo } from './session-info'
import { SessionPlots } from './session-plots'
import { StarButton } from './star-button'
import { TimelineSlider } from './timeline-slider/timeline-slider'
import { ViewSettings } from './view-settings'
import { ZoomSettings } from './zoom-settings'

const TABS = {
  SESSION: 'session',
  CAPTURE: 'capture',
  CHARTS: 'charts',
}

export const SessionDetailsPage = () => {
  const { id } = useParams()
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)
  const { activeOccurrences } = useActiveOccurrences()
  const { activeCaptureId } = useActiveCaptureId()
  const { session, isLoading, error } = useSessionDetails(id as string, {
    capture: activeCaptureId,
    occurrence: activeOccurrences[0],
  })

  useEffect(() => {
    setDetailBreadcrumb(session ? { title: session.label } : undefined)

    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [session])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[320px]">
        <LoadingSpinner />
      </div>
    )
  }

  if (!session || error) {
    return <ErrorState error={error} />
  }

  return (
    <>
      {session.exampleCaptures[0] ? (
        <Helmet>
          <meta name="og:image" content={session.exampleCaptures[0]?.src} />
        </Helmet>
      ) : null}
      <Content session={session} />
    </>
  )
}

const Content = ({ session }: { session: SessionDetails }) => {
  // Settings
  const [poll, setPoll] = useState(false)
  const transformRef = useRef<ReactZoomPanPinchRef>(null)
  const [settings, setSettings] = useState({
    defaultFilters: true,
    showDetections: true,
  })

  // Data
  const { projectId } = useParams()
  const { user } = useUser()
  const { activeCaptureId, setActiveCaptureId } = useActiveCaptureId(
    session.firstCapture?.id
  )
  const { capture: activeCapture } = useCaptureDetails({
    id: activeCaptureId as string,
    poll,
    projectId: projectId as string,
  })
  const { timeline = [] } = useSessionTimeline(session.id)

  useEffect(() => {
    // If the active capture has a job in progress, we want to poll the endpoint so we can show job updates
    if (activeCapture?.hasJobInProgress) {
      setPoll(true)
    } else {
      setPoll(false)
    }
  }, [activeCapture])

  if (!session.firstCapture) {
    return null
  }

  return (
    <>
      <PageHeader
        title={session.label}
        subTitle={translate(STRING.RESULTS_CAPTURES, {
          total: session?.numImages ?? 0,
        })}
        tooltip={translate(STRING.TOOLTIP_SESSION)}
      >
        {user.loggedIn ? <Process capture={activeCapture} /> : null}
      </PageHeader>
      <div className="grid grid-cols-1 gap-4 mt-6 md:grid-cols-[auto_1fr] md:gap-6">
        <Box className="order-last p-2 bg-background rounded-lg md:order-first md:p-4 md:rounded-xl">
          <Tabs.Root defaultValue={TABS.SESSION}>
            <Tabs.List>
              <Tabs.Trigger
                value={TABS.SESSION}
                label={translate(STRING.TAB_ITEM_SESSION)}
              />
              <Tabs.Trigger
                value={TABS.CAPTURE}
                label={translate(STRING.TAB_ITEM_CAPTURE)}
              />
              <Tabs.Trigger
                value={TABS.CHARTS}
                label={translate(STRING.TAB_ITEM_CHARTS)}
              />
            </Tabs.List>
            <Tabs.Content value={TABS.SESSION}>
              <div className="w-72">
                <SessionInfo session={session} />
              </div>
            </Tabs.Content>
            <Tabs.Content value={TABS.CAPTURE}>
              <div className="w-72">
                {activeCapture ? <CaptureInfo capture={activeCapture} /> : null}
              </div>
            </Tabs.Content>
            <Tabs.Content className="overflow-x-auto" value={TABS.CHARTS}>
              <div className="w-96 grid gap-6">
                <SessionPlots session={session} />
              </div>
            </Tabs.Content>
          </Tabs.Root>
        </Box>
        <div className="grow flex flex-col bg-background rounded-lg border border-border overflow-hidden md:rounded-xl">
          <div className="grow flex items-center justify-center bg-foreground">
            <Capture
              defaultFilters={settings.defaultFilters}
              detections={activeCapture?.detections ?? []}
              height={activeCapture?.height ?? session.firstCapture.height}
              showDetections={settings.showDetections}
              src={activeCapture?.url}
              transformRef={transformRef}
              width={activeCapture?.width ?? session.firstCapture.width}
            />
          </div>
          <div className="flex flex-col flex-wrap justify-between gap-2 p-2 border-t border-border md:flex-row md:p-6">
            <div className="min-h-8 flex-1 flex items-center gap-2">
              {activeCapture ? (
                <>
                  <span className="pt-0.5 text-muted-foreground truncate">
                    {activeCapture.dateTimeLabel}
                  </span>
                  <StarButton
                    capture={activeCapture}
                    canStar={user.loggedIn && activeCapture.canStar}
                  />
                  <BasicTooltip
                    asChild
                    content={translate(STRING.TOOLTIP_VIEW_SOURCE_FILE)}
                  >
                    <a
                      href={activeCapture.url}
                      className={cn(
                        buttonVariants({ size: 'icon', variant: 'ghost' })
                      )}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <ExternalLinkIcon className="w-4 h-4" />
                    </a>
                  </BasicTooltip>
                </>
              ) : (
                <span className="pt-0.5 text-muted-foreground truncate">
                  {translate(STRING.LOADING_DATA)}...
                </span>
              )}
            </div>
            <div className="flex items-center md:justify-center">
              <CaptureNavigation
                activeCapture={activeCapture}
                timeline={timeline}
                setActiveCaptureId={setActiveCaptureId}
              />
            </div>
            <div className="flex-1 flex items-center gap-2 md:justify-end">
              <ZoomSettings transformRef={transformRef} />
              <ViewSettings
                onSettingsChange={setSettings}
                settings={settings}
              />
            </div>
          </div>
        </div>
        <div className="p-2 bg-background rounded-lg border border-border overflow-hidden md:col-span-2 md:p-4">
          <ActivityPlot
            session={session}
            setActiveCaptureId={setActiveCaptureId}
            timeline={timeline}
          />
          <TimelineSlider
            activeCapture={activeCapture}
            session={session}
            setActiveCaptureId={setActiveCaptureId}
            timeline={timeline}
          />
        </div>
      </div>
    </>
  )
}

export default SessionDetailsPage
