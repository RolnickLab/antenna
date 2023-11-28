import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { CaptureDetails } from 'data-services/models/capture-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const StarButton = ({
  captureId,
  capture,
}: {
  captureId: string
  capture?: CaptureDetails
}) => {
  const isStarred = capture?.isStarred ?? false
  const { starCapture, isLoading } = useStarCapture(captureId, isStarred)
  const disabled = isLoading

  return (
    <Button
      disabled={disabled}
      icon={isStarred ? IconType.HeartFilled : IconType.Heart}
      label={isStarred ? translate(STRING.STARRED) : translate(STRING.STAR)}
      loading={isLoading}
      theme={ButtonTheme.Neutral}
      onClick={() => starCapture()}
    />
  )
}
