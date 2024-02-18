import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails } from 'data-services/models/capture-details'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const StarButton = ({
  capture,
  captureFetching,
  captureId,
}: {
  capture?: CaptureDetails
  captureFetching?: boolean
  captureId: string
}) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const isStarred = capture?.isStarred ?? false
  const { starCapture, isLoading } = useStarCapture(captureId, isStarred)
  const tooltipContent = project?.canUpdate
    ? isStarred
      ? translate(STRING.STARRED)
      : translate(STRING.STAR)
    : translate(STRING.MESSAGE_PERMISSIONS_MISSING)

  return (
    <Tooltip content={tooltipContent}>
      <IconButton
        icon={isStarred ? IconType.HeartFilled : IconType.Heart}
        disabled={!project?.canUpdate}
        loading={isLoading || captureFetching}
        theme={IconButtonTheme.Neutral}
        onClick={() => starCapture()}
      />
    </Tooltip>
  )
}
