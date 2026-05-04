import { Occurrence } from 'data-services/models/occurrence'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { IdentificationScore } from 'nova-ui-kit'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { IdQuickActions } from 'pages/occurrence-details/id-quick-actions/id-quick-actions'
import { SuggestIdPopover } from 'pages/occurrence-details/suggest-id/suggest-id-popover'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'

export const OccurrenceActions = ({
  item,
  showScore,
  showActions,
}: {
  item: Occurrence
  showActions?: boolean
  showScore?: boolean
}) => {
  const { userInfo } = useUserInfo()
  const canUpdate = item.userPermissions.includes(UserPermission.Update)
  const agreed = userInfo ? item.userAgreed(userInfo.id) : false

  return (
    <div className="flex flex-wrap items-center justify-start gap-2">
      {showScore && item.determinationScore !== undefined ? (
        <BasicTooltip
          content={
            item.determinationVerified
              ? translate(STRING.VERIFIED_BY, {
                  name: item.determinationVerifiedBy?.name,
                })
              : translate(STRING.MACHINE_PREDICTION_SCORE, {
                  score: `${item.determinationScore}`,
                })
          }
        >
          <IdentificationScore
            confirmed={item.determinationVerified}
            confidenceScore={item.determinationScore}
          />
        </BasicTooltip>
      ) : null}
      {showActions && canUpdate ? (
        <>
          <Agree
            agreed={agreed}
            agreeWith={{
              identificationId: item.determinationIdentificationId,
              predictionId: item.determinationPredictionId,
            }}
            applied
            compact
            occurrenceId={item.id}
            taxonId={item.determinationTaxon.id}
          />
          <SuggestIdPopover occurrenceIds={[item.id]} />
          <IdQuickActions
            occurrenceIds={[item.id]}
            occurrenceTaxa={[item.determinationTaxon]}
          />
        </>
      ) : null}
    </div>
  )
}
