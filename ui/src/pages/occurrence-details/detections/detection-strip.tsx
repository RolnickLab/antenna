import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import {
  OccurrenceDetails,
  OccurrenceDetection,
} from 'data-services/models/occurrence-details'
import { buttonVariants } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { Link, useLocation } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { DetectionCaption } from './detection-caption'

const JumpLink = ({
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

/** Every detection of an occurrence, earliest capture first, each linked to its capture. */
export const DetectionStrip = ({
  occurrence,
  onNavigate,
  projectId,
}: {
  occurrence: OccurrenceDetails
  /** Called when a link to a capture is followed, so a dialog around this can close. */
  onNavigate?: () => void
  projectId: string
}) => {
  const { pathname, search } = useLocation()
  const detections = occurrence.detections
  const total = detections.length
  const first = detections[0]
  const last = detections[total - 1]

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

  const renderDetection = (detection: OccurrenceDetection) => (
    <BlueprintItem
      caption={
        <DetectionCaption
          detectionId={detection.id}
          label={detection.detectionLabel}
          timeLabel={detection.timeLabel}
        />
      }
      item={{ ...detection, to: sessionLink(detection.captureId) }}
      key={detection.id}
      onLinkClick={onNavigate}
    />
  )

  return (
    <BlueprintCollection filmStrip showLicenseInfo={total > 0}>
      {total ? (
        <div className="flex flex-wrap items-center justify-between gap-1 pb-2">
          <span className="body-small text-muted-foreground">
            {total === 1
              ? translate(STRING.DETECTIONS_ONE)
              : translate(STRING.DETECTIONS_COUNT, { count: total })}
          </span>
          {total > 1 ? (
            <div className="flex flex-wrap items-center gap-1">
              <JumpLink
                label={translate(STRING.FIRST_DETECTION)}
                onClick={onNavigate}
                to={sessionLink(first?.captureId)}
              />
              <JumpLink
                label={translate(STRING.LAST_DETECTION)}
                onClick={onNavigate}
                to={sessionLink(last?.captureId)}
              />
            </div>
          ) : null}
        </div>
      ) : null}
      {detections.map(renderDetection)}
    </BlueprintCollection>
  )
}
