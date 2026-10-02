import { isGenusOrBelow } from 'components/taxon-details/utils'
import { FrameLabel } from 'data-services/models/occurrence-details'
import { Taxon } from 'data-services/models/taxa'
import { BanIcon } from 'lucide-react'
import { cn } from 'nova-ui-kit/utils'
import { STRING, translate } from 'utils/language'

export const FrameTaxonName = ({ taxon }: { taxon?: Taxon }) => {
  const name = taxon?.name ?? translate(STRING.TRACK_FRAME_NO_CLASSIFICATION)

  return (
    <span
      className={cn(
        'break-words',
        taxon ? 'text-foreground' : 'text-muted-foreground',
        { italic: !!taxon && isGenusOrBelow(taxon) }
      )}
      title={name}
    >
      {name}
    </span>
  )
}

/**
 * Beside a frame's crop: which detection and when, then the classifier's name for it.
 * `hasVector` is undefined when the payload did not say, and only a definite no is marked.
 */
export const FrameCaption = ({
  detectionId,
  hasVector,
  label,
  timeLabel,
}: {
  detectionId: string
  hasVector?: boolean
  label: FrameLabel
  timeLabel: string
}) => (
  <div className="flex flex-col gap-0.5 body-small">
    <div className="flex items-baseline justify-between gap-2 text-muted-foreground tabular-nums whitespace-nowrap">
      <div className="flex items-center gap-1">
        <span
          title={translate(STRING.TRACK_FRAME_DETECTION, { id: detectionId })}
        >
          #{detectionId}
        </span>
        {hasVector === false ? (
          <span
            className="flex items-center"
            title={translate(STRING.TRACK_FRAME_NO_VECTOR)}
          >
            <BanIcon
              aria-label={translate(STRING.TRACK_FRAME_NO_VECTOR)}
              className="w-3 h-3"
            />
          </span>
        ) : null}
      </div>
      <span>{timeLabel}</span>
    </div>
    <span className="font-medium">
      <FrameTaxonName taxon={label.taxon} />
      {label.taxon || label.score !== undefined ? (
        <>
          {' '}
          <span className="text-foreground tabular-nums whitespace-nowrap">
            ({label.score?.toFixed(2) ?? translate(STRING.VALUE_NOT_AVAILABLE)})
          </span>
        </>
      ) : null}
    </span>
  </div>
)
