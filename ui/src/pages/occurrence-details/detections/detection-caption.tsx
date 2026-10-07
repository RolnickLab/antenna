import { isGenusOrBelow } from 'components/taxon-details/utils'
import { DetectionLabel } from 'data-services/models/occurrence-details'
import { cn } from 'nova-ui-kit/utils'
import { STRING, translate } from 'utils/language'

/** Beside a detection's crop: which detection and when, then the classifier's name for it. */
export const DetectionCaption = ({
  detectionId,
  label,
  timeLabel,
}: {
  detectionId: string
  label: DetectionLabel
  timeLabel: string
}) => {
  const name =
    label.taxon?.name ?? translate(STRING.DETECTION_NO_CLASSIFICATION)

  return (
    <div className="flex flex-col gap-0.5 body-small">
      <div className="flex items-baseline justify-between gap-2 text-muted-foreground tabular-nums whitespace-nowrap">
        <span title={translate(STRING.DETECTION_NUMBER, { id: detectionId })}>
          #{detectionId}
        </span>
        <span>{timeLabel}</span>
      </div>
      <span className="font-medium">
        <span
          className={cn(
            'break-words',
            label.taxon ? 'text-foreground' : 'text-muted-foreground',
            { italic: !!label.taxon && isGenusOrBelow(label.taxon) }
          )}
          title={name}
        >
          {name}
        </span>
        {label.taxon ? (
          <>
            {' '}
            <span className="text-foreground tabular-nums whitespace-nowrap">
              (
              {label.score?.toFixed(2) ?? translate(STRING.VALUE_NOT_AVAILABLE)}
              )
            </span>
          </>
        ) : null}
      </span>
    </div>
  )
}
