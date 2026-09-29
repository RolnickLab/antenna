import { CaptureDetails } from 'data-services/models/capture-details'
import { InfoBlock } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useProjectFeature } from 'utils/project-features/useProjectFeature'

export const CaptureInfo = ({ capture }: { capture: CaptureDetails }) => {
  const { projectId } = useParams()
  const trackingEnabled = useProjectFeature('tracking')
  const { detectionsValid, detectionsWithFeatures } = capture
  // Only worth a row when a box is missing a vector; tracking skips those boxes.
  const vectorField =
    trackingEnabled &&
    detectionsValid !== undefined &&
    detectionsWithFeatures !== undefined &&
    detectionsWithFeatures < detectionsValid
      ? {
          label: translate(STRING.FIELD_LABEL_BOXES_WITH_VECTORS),
          value: translate(STRING.VALUE_COUNT_OF_TOTAL, {
            count: detectionsWithFeatures,
            total: detectionsValid,
          }),
        }
      : undefined

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
    ...(vectorField ? [vectorField] : []),
  ]

  return <InfoBlock fields={fields} />
}
