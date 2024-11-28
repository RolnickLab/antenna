import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { FilterProps } from './types'

export const ImageFilter = ({ value }: FilterProps) => {
  const { capture, isLoading } = useCaptureDetails(value)

  const label = (() => {
    if (capture) {
      return `#${capture.id}`
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return 'All images'
  })()

  return (
    <div className="px-2 pt-0.5">
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
