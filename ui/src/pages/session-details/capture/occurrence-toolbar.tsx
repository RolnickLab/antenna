import { DeterminationScore } from 'components/determination-score'
import { PathFrame } from 'data-services/models/occurrence-path'
import { Loader2Icon, RouteIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

export interface ToolbarOccurrence {
  frameCount: number
  groupingVerified: boolean
  groupingVerifiedAt: Date | null
  groupingVerifiedBy: string | null
  id: string
  label: string
  score: number
  scoreLabel: string
}

/**
 * The control anchored under a selected occurrence's box.
 *
 * Editing actions appear only once the path is on screen, so nobody restructures an
 * occurrence on evidence they have not seen. Merge is the exception and stays
 * available throughout: a stray single frame joins a chain that way.
 */
export const OccurrenceToolbar = ({
  isLoadingPath,
  occurrence,
  onHidePath,
  onMerge,
  onOpenOccurrence,
  onShowPath,
  onSplit,
  onVerify,
  path,
  pathError,
  shownFrames,
}: {
  isLoadingPath?: boolean
  occurrence: ToolbarOccurrence
  onHidePath: () => void
  onMerge: () => void
  onOpenOccurrence: () => void
  onShowPath: () => void
  onSplit: () => void
  onVerify: () => void
  path?: PathFrame[]
  /** The last request for this occurrence's path failed; the show button retries. */
  pathError?: boolean
  /** Ghost boxes actually drawn, which the trail caps below the path's length. */
  shownFrames?: number
}) => {
  const singleFrame = occurrence.frameCount <= 1
  const pathShown = !!path?.length

  const subtitle = () => {
    if (!pathShown) {
      return singleFrame
        ? translate(STRING.TRACK_SINGLE_FRAME_NO_PATH)
        : translate(STRING.TRACK_FRAMES_COUNT, { count: occurrence.frameCount })
    }

    const times = path
      .map((frame) => frame.timestamp)
      .filter((timestamp): timestamp is Date => !!timestamp)

    if (!times.length) {
      return translate(STRING.TRACK_FRAMES_COUNT, { count: path.length })
    }

    return translate(STRING.TRACK_PATH_RANGE, {
      count: path.length,
      end: getFormatedTimeString({ date: times[times.length - 1] }),
      start: getFormatedTimeString({ date: times[0] }),
    })
  }

  return (
    <div className="flex flex-col items-start gap-2 min-w-48 max-w-80">
      <button
        className="body-base text-primary font-medium text-left"
        onClick={onOpenOccurrence}
      >
        <span>{occurrence.label}</span>
      </button>

      <div className="flex items-center gap-2">
        <DeterminationScore
          score={occurrence.score}
          scoreLabel={occurrence.scoreLabel}
          verified={occurrence.score === 1}
        />
        <span className="body-small text-muted-foreground">{subtitle()}</span>
      </div>

      {occurrence.groupingVerified ? (
        <span className="body-small text-muted-foreground">
          {translate(STRING.TRACK_GROUPING_CONFIRMED_BY, {
            date: occurrence.groupingVerifiedAt
              ? getFormatedDateTimeString({
                  date: occurrence.groupingVerifiedAt,
                })
              : translate(STRING.VALUE_NOT_AVAILABLE),
            name:
              occurrence.groupingVerifiedBy ?? translate(STRING.ANONYMOUS_USER),
          })}
        </span>
      ) : null}

      {shownFrames !== undefined && path && shownFrames < path.length ? (
        <span className="body-small text-muted-foreground">
          {translate(STRING.TRACK_SHOWING_PART_OF_PATH, {
            shown: shownFrames,
            total: path.length,
          })}
        </span>
      ) : null}

      {pathError && !pathShown && !isLoadingPath ? (
        <span className="body-small text-destructive" role="alert">
          {translate(STRING.TRACK_PATH_ERROR)}
        </span>
      ) : null}

      <div className="flex flex-wrap items-center gap-1">
        {pathShown ? (
          <Button onClick={onHidePath} size="small" variant="ghost">
            <span>{translate(STRING.TRACK_HIDE_PATH)}</span>
          </Button>
        ) : null}

        {/* A single frame has no path to draw, and the subtitle says so. */}
        {!pathShown && !singleFrame ? (
          <Button
            disabled={isLoadingPath}
            onClick={onShowPath}
            size="small"
            variant="ghost"
          >
            {isLoadingPath ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : (
              <RouteIcon className="w-4 h-4" />
            )}
            <span>
              {isLoadingPath
                ? translate(STRING.TRACK_LOADING_PATH)
                : translate(STRING.TRACK_SHOW_PATH)}
            </span>
          </Button>
        ) : null}

        {pathShown ? (
          <Button onClick={onSplit} size="small" variant="ghost">
            <span>{translate(STRING.TRACK_SPLIT_HERE)}</span>
          </Button>
        ) : null}

        <Button onClick={onMerge} size="small" variant="ghost">
          <span>{translate(STRING.TRACK_MERGE)}</span>
        </Button>

        {pathShown ? (
          <Button onClick={onVerify} size="small" variant="ghost">
            <span>
              {occurrence.groupingVerified
                ? translate(STRING.TRACK_UNDO_CONFIRMATION)
                : translate(STRING.TRACK_CONFIRM_GROUPING)}
            </span>
          </Button>
        ) : null}
      </div>
    </div>
  )
}
