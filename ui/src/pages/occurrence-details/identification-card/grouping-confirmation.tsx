import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { UserIcon } from 'lucide-react'
import { IdentificationCard } from 'nova-ui-kit'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'

export const GroupingConfirmation = ({
  occurrence,
}: {
  occurrence: Occurrence
}) => {
  const user = occurrence.groupingVerifiedBy
  const formattedTime = occurrence.groupingVerifiedAt
    ? getFormatedDateTimeString({ date: occurrence.groupingVerifiedAt })
    : translate(STRING.VALUE_NOT_AVAILABLE)

  return (
    <div>
      <span className="block p-2 text-right text-muted-foreground body-overline-small normal-case">
        {formattedTime}
      </span>
      <IdentificationCard
        avatar={
          user?.image?.length ? (
            <img alt="" src={user.image} />
          ) : (
            <UserIcon className="w-4 h-4 text-generic-white" />
          )
        }
        subTitle={translate(STRING.TRACK_GROUPING_CONFIRMED_BY, {
          date: formattedTime,
          name: user?.name ?? translate(STRING.ANONYMOUS_USER),
        })}
        title={translate(STRING.TRACK_GROUPING_CONFIRMED)}
      />
    </div>
  )
}
