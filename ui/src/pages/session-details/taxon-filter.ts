import { CaptureDetection } from 'data-services/models/capture'

export const filterDetectionsByTaxon = (
  detections: CaptureDetection[],
  taxonId?: string
) => {
  if (!taxonId) {
    return detections
  }

  return detections.filter((detection) =>
    detection.determinationTaxonIds.includes(taxonId)
  )
}
