import { TrackCompleteReviewEntry } from 'data-services/models/occurrence-history'
import { UserIcon } from 'lucide-react'
import { IdentificationCard } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { getUserLabel } from 'utils/user/getUserLabel'
import { UserInfo } from 'utils/user/types'
import {
  HistoryStat,
  HistoryStats,
  HistoryTime,
  HistoryTypeBadge,
} from './history-stats'

export const TrackReview = ({
  currentUser,
  entry,
}: {
  currentUser?: UserInfo
  entry: TrackCompleteReviewEntry
}) => {
  const { projectId } = useParams()
  const { payload, user } = entry
  const added = payload.detections_added.length
  const removed = payload.detections_removed.length

  const stats: HistoryStat[] = [
    {
      label: translate(STRING.TRACK_SUMMARY_FRAMES),
      value:
        payload.frames_count === 1
          ? translate(STRING.TRACK_FRAMES_ONE)
          : translate(STRING.TRACK_FRAMES_COUNT, {
              count: payload.frames_count,
            }),
    },
  ]
  if (payload.first_timestamp && payload.last_timestamp) {
    stats.push({
      label: translate(STRING.HISTORY_TIME_SPAN),
      value: getCompactTimespanString({
        date1: new Date(payload.first_timestamp),
        date2: new Date(payload.last_timestamp),
        options: { second: true },
      }),
    })
  }

  return (
    <div>
      <HistoryTime
        label={getFormatedDateTimeString({ date: new Date(entry.timestamp) })}
      />
      <IdentificationCard
        avatar={
          user?.image?.length ? (
            <img alt="" src={user.image} />
          ) : (
            <UserIcon className="w-4 h-4 text-generic-white" />
          )
        }
        subTitle={
          added || removed
            ? translate(STRING.HISTORY_REVIEW_CHANGES, { added, removed })
            : undefined
        }
        title={translate(STRING.HISTORY_TRACK_COMPLETE_BY, {
          name: getUserLabel(user, currentUser),
        })}
        titleAddon={
          <HistoryTypeBadge label={translate(STRING.HISTORY_REVIEW)} />
        }
      >
        <HistoryStats stats={stats} />
        {payload.split_from_occurrence_id ? (
          <div className="px-4 pb-4 body-small">
            <Link
              className="underline underline-offset-4 text-muted-foreground"
              to={APP_ROUTES.OCCURRENCE_DETAILS({
                projectId: projectId as string,
                occurrenceId: `${payload.split_from_occurrence_id}`,
              })}
            >
              {translate(STRING.HISTORY_SPLIT_FROM, {
                id: `${payload.split_from_occurrence_id}`,
              })}
            </Link>
          </div>
        ) : null}
      </IdentificationCard>
    </div>
  )
}
