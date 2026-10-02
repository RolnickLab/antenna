import { CommentReviewEntry } from 'data-services/models/occurrence-history'
import { UserIcon } from 'lucide-react'
import { IdentificationCard } from 'nova-ui-kit'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { getUserLabel } from 'utils/user/getUserLabel'
import { UserInfo } from 'utils/user/types'
import { HistoryTime, HistoryTypeBadge } from './history-stats'

export const CommentReview = ({
  currentUser,
  entry,
}: {
  currentUser?: UserInfo
  entry: CommentReviewEntry
}) => (
  <div>
    <HistoryTime
      label={getFormatedDateTimeString({ date: new Date(entry.timestamp) })}
    />
    <IdentificationCard
      avatar={
        entry.user?.image?.length ? (
          <img alt="" src={entry.user.image} />
        ) : (
          <UserIcon className="w-4 h-4 text-generic-white" />
        )
      }
      subTitle={
        entry.withdrawn ? translate(STRING.HISTORY_WITHDRAWN) : undefined
      }
      title={translate(STRING.HISTORY_COMMENT_BY, {
        name: getUserLabel(entry.user, currentUser),
      })}
      titleAddon={<HistoryTypeBadge label={translate(STRING.HISTORY_COMMENT)} />}
    >
      <p className="px-4 py-4 border-border border-t body-small whitespace-pre-wrap">
        {entry.comment}
      </p>
    </IdentificationCard>
  </div>
)
