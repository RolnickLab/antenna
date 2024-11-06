import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { ChevronDownIcon, Loader2 } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'event'

export const SessionFilter = () => {
  const { filters } = useFilters()
  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value
  const { session, isLoading } = useSessionDetails(value)

  const triggerLabel = (() => {
    if (session) {
      return session.label
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return 'All sessions'
  })()

  return (
    <Button
      disabled
      variant="outline"
      className="w-full justify-between text-muted-foreground font-normal"
    >
      <>
        <span>{triggerLabel}</span>
        {isLoading && value ? (
          <Loader2 className="h-4 w-4 ml-2 animate-spin" />
        ) : (
          <ChevronDownIcon className="h-4 w-4 ml-2" />
        )}
      </>
    </Button>
  )
}
