import { useSessionDetails } from 'data-services/hooks/sessions/useSessionDetails'
import { FilterProps } from './types'

export const SessionFilter = ({ value }: FilterProps) => {
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
