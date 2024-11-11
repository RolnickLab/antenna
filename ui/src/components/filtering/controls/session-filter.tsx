import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'event'

export const SessionFilter = () => {
  const { filters } = useFilters()
  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value
  const { session, isLoading } = useSessionDetails(value)

  const label = (() => {
    if (session) {
      return session.label
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return 'All sessions'
  })()

  return (
    <div className="px-2">
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
