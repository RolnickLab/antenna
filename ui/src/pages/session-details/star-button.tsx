import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { CaptureDetails as Capture } from 'data-services/models/capture-details'
import { Loader2Icon, StarIcon } from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const StarButton = ({
  capture,
  canStar,
}: {
  capture: Capture
  canStar: boolean
}) => {
  const isStarred = capture.isStarred ?? false
  const { starCapture, isLoading } = useStarCapture(capture.id, isStarred)

  if (!canStar) {
    return null
  }

  return (
    <BasicTooltip
      asChild
      content={isStarred ? translate(STRING.STARRED) : translate(STRING.STAR)}
    >
      <Button
        disabled={isLoading}
        aria-label={
          isStarred ? translate(STRING.STARRED) : translate(STRING.STAR)
        }
        onClick={() => starCapture()}
        size="icon"
        variant="ghost"
      >
        {isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <StarIcon
            className="w-4 h-4 transition-colors"
            fill={isStarred ? 'currentColor' : 'transparent'}
          />
        )}
      </Button>
    </BasicTooltip>
  )
}
