import { FilterProps } from './types'

export const OccurrenceFilter = ({ value }: FilterProps) => (
  <div className="pt-0.5">
    <span className="text-muted-foreground">{value ? `#${value}` : ''}</span>
  </div>
)
