import { isGenusOrBelow } from 'components/taxon-details/utils'
import { DetectionLabel } from 'data-services/models/occurrence-details'
import { ImageIcon } from 'lucide-react'
import { cn } from 'nova-ui-kit/utils'
import { STRING, translate } from 'utils/language'

/** Beside a detection's crop: which detection and when, then the classifier's name for it. */
export const DetectionCaption = ({
  captureUrl,
  detectionId,
  label,
  timeLabel,
}: {
  /** The whole capture this detection was cropped from, opened at full size. */
  captureUrl?: string
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
        <div className="flex items-center gap-1">
          <span>{timeLabel}</span>
          {captureUrl ? (
            <a
              aria-label={translate(STRING.OPEN_FULL_CAPTURE)}
              className="flex items-center hover:text-foreground"
              href={captureUrl}
              rel="noreferrer"
              target="_blank"
              title={translate(STRING.OPEN_FULL_CAPTURE)}
            >
              <ImageIcon aria-hidden className="w-3 h-3" />
            </a>
          ) : null}
        </div>
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
