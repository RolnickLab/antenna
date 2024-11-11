import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'detections__source_image'

export const ImageFilter = () => {
  const { filters } = useFilters()
  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value
  const { capture, isLoading } = useCaptureDetails(value)

  const label = (() => {
    if (capture) {
      return capture?.dateTimeLabel
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return 'All images'
  })()

  return (
    <div className="px-2">
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
