import { CaptureDetails } from 'data-services/models/capture-details'
import { InfoBlock } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const CaptureInfo = ({ capture }: { capture: CaptureDetails }) => {
  const { projectId } = useParams()

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_ID),
      value: capture.id,
    },
    {
      label: translate(STRING.FIELD_LABEL_FILE_SIZE),
      value: capture.fileSize,
    },
    {
      label: translate(STRING.FIELD_LABEL_RESOLUTION),
      value: capture.dimensionsLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_FILENAME),
      value: capture.filename,
    },
    {
      label: translate(STRING.FIELD_LABEL_PATH),
      value: capture.path,
    },
    {
      label: translate(STRING.FIELD_LABEL_OCCURRENCES),
      value: capture.numOccurrences,
      to: getAppRoute({
        to: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        filters: { detections__source_image: capture.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_TAXA),
      value: capture.numTaxa,
    },
  ]

  return <InfoBlock fields={fields} />
}
