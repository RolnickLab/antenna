import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { useOccurrenceFrames } from 'data-services/hooks/occurrences/useOccurrenceFrames'
import {
  OccurrenceDetails,
  OccurrenceFrame,
} from 'data-services/models/occurrence-details'
import {
  FIRST_FRAME_PAGE,
  FramePageRequest,
  getFrameRange,
  isFirstFramePage,
} from 'data-services/models/occurrence-frames-page'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from 'lucide-react'
import { Button, buttonVariants } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { ReactNode, useEffect, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { FrameCaption } from './frame-caption'
import { FrameMenu } from './frame-menu'
import { PendingFrameAction } from './types'

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

const PageButton = ({
  children,
  label,
  onClick,
}: {
  children: ReactNode
  label: string
  onClick?: () => void
}) => (
  <Button
    aria-label={label}
    disabled={!onClick}
    onClick={onClick}
    size="icon"
    title={label}
    variant="ghost"
  >
    {children}
  </Button>
)

/** The track's frames one page at a time, earliest first, opened on the linked detection. */
export const FrameStrip = ({
  canRestructure,
  occurrence,
  onAction,
  onNavigate,
  projectId,
  trackingEnabled,
}: {
  canRestructure: boolean
  occurrence: OccurrenceDetails
  onAction: (action: PendingFrameAction) => void
  onNavigate?: () => void
  projectId: string
  trackingEnabled: boolean
}) => {
  const { pathname, search } = useLocation()
  const [searchParams] = useSearchParams()
  const selectedId = searchParams.get('detection') ?? undefined
  const [request, setRequest] = useState<FramePageRequest>(() =>
    selectedId ? { around: selectedId } : FIRST_FRAME_PAGE
  )
  const onFirstPage = isFirstFramePage(request)
  const page = useOccurrenceFrames({
    enabled: !onFirstPage,
    occurrenceId: occurrence.id,
    request,
  })

  // A detection link can name a frame of another occurrence, which has no page here,
  // and a track edit can leave the open page past the end.
  useEffect(() => {
    if (
      ('around' in request && page.error) ||
      (page.frames && !page.frames.length && page.total)
    ) {
      setRequest(FIRST_FRAME_PAGE)
    }
  }, [page.error, page.frames, page.total, request])

  const total = onFirstPage ? occurrence.numDetections : page.total ?? 0
  const frames = (onFirstPage ? occurrence.firstFramesPage : page.frames) ?? []
  const range = getFrameRange(frames)
  const next = onFirstPage
    ? frames.length < total
      ? { offset: frames.length }
      : undefined
    : page.next
  const previous = onFirstPage ? undefined : page.previous
  const lastFrame = occurrence.lastFrame
  const onLastPage = !next

  const sessionRoute = occurrence.sessionId
    ? APP_ROUTES.SESSION_DETAILS({
        projectId,
        sessionId: occurrence.sessionId,
      })
    : undefined

  const sessionLink = (captureId?: string) => {
    if (!sessionRoute || !captureId) {
      return undefined
    }

    // On the session page itself, keep the other selected occurrences and only move
    // the capture.
    if (pathname === sessionRoute) {
      const params = new URLSearchParams(search)
      if (!params.getAll('occurrence').includes(occurrence.id)) {
        params.append('occurrence', occurrence.id)
      }
      params.set('capture', captureId)

      return `${sessionRoute}?${params}`
    }

    return getAppRoute({
      to: sessionRoute,
      filters: { occurrence: occurrence.id, capture: captureId },
    })
  }

  const renderFrame = (frame: OccurrenceFrame) => (
    <BlueprintItem
      actions={
        trackingEnabled && canRestructure ? (
          <FrameMenu
            isFirstInTime={frame.frameIndex === 0}
            isOnlyFrame={total < 2}
            onAction={(action) =>
              onAction({
                action,
                detectionId: frame.id,
                movedBySplit: total - frame.frameIndex,
                timeLabel: frame.timeLabel,
                total,
              })
            }
          />
        ) : undefined
      }
      caption={
        trackingEnabled ? (
          <FrameCaption
            detectionId={frame.id}
            hasVector={frame.hasVector}
            label={frame.frameLabel}
            timeLabel={frame.timeLabel}
          />
        ) : undefined
      }
      item={{
        ...frame,
        countLabel: '',
        to: sessionLink(frame.captureId),
      }}
      key={frame.id}
      onLinkClick={onNavigate}
      selected={frame.id === selectedId}
    />
  )

  return (
    <BlueprintCollection
      filmStrip={trackingEnabled}
      showLicenseInfo={total > 0}
    >
      {trackingEnabled && total ? (
        <div className="flex flex-wrap items-center justify-between gap-1 pb-2">
          <span className="body-small text-muted-foreground">
            {total === 1
              ? translate(STRING.TRACK_FRAMES_ONE)
              : translate(STRING.TRACK_FRAMES_COUNT, { count: total })}
          </span>
          <div className="flex flex-wrap items-center gap-1">
            {total === 1 ? (
              <JumpToFrame
                label={translate(STRING.TRACK_JUMP_ONLY_FRAME)}
                onClick={onNavigate}
                to={sessionLink(lastFrame?.captureId)}
              />
            ) : (
              <>
                <JumpToFrame
                  label={translate(STRING.TRACK_JUMP_FIRST_FRAME)}
                  onClick={onNavigate}
                  to={sessionLink(occurrence.firstFrame?.captureId)}
                />
                <JumpToFrame
                  label={translate(STRING.TRACK_JUMP_LAST_FRAME)}
                  onClick={onNavigate}
                  to={sessionLink(lastFrame?.captureId)}
                />
              </>
            )}
          </div>
        </div>
      ) : null}
      {range && (previous || next) ? (
        <div className="flex flex-wrap items-center justify-between gap-1 pb-2">
          <span className="body-small text-muted-foreground" aria-live="polite">
            {translate(STRING.TRACK_FRAMES_RANGE, { ...range, total })}
          </span>
          <div className="flex items-center gap-1">
            <PageButton
              label={translate(STRING.TRACK_FRAMES_PAGE_FIRST)}
              onClick={
                previous ? () => setRequest(FIRST_FRAME_PAGE) : undefined
              }
            >
              <ChevronsLeftIcon className="w-4 h-4" />
            </PageButton>
            <PageButton
              label={translate(STRING.TRACK_FRAMES_PAGE_EARLIER)}
              onClick={previous ? () => setRequest(previous) : undefined}
            >
              <ChevronLeftIcon className="w-4 h-4" />
            </PageButton>
            <PageButton
              label={translate(STRING.TRACK_FRAMES_PAGE_LATER)}
              onClick={next ? () => setRequest(next) : undefined}
            >
              <ChevronRightIcon className="w-4 h-4" />
            </PageButton>
            <PageButton
              label={translate(STRING.TRACK_FRAMES_PAGE_LAST)}
              onClick={
                !onLastPage && lastFrame
                  ? () => setRequest({ around: lastFrame.id })
                  : undefined
              }
            >
              <ChevronsRightIcon className="w-4 h-4" />
            </PageButton>
          </div>
        </div>
      ) : null}
      {page.error && !('around' in request) ? (
        <p className="body-small text-destructive pb-2">
          {translate(STRING.TRACK_FRAMES_PAGE_ERROR)}
        </p>
      ) : null}
      {frames.map(renderFrame)}
    </BlueprintCollection>
  )
}
