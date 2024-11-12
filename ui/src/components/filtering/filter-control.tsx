import { X } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { AVAILABLE_FILTERS, useFilters } from 'utils/useFilters'
import { CollectionFilter } from './filters/collection-filter'
import { ImageFilter } from './filters/image-filter'
import { ScoreFilter } from './filters/score-filter'
import { SessionFilter } from './filters/session-filter'
import { StationFilter } from './filters/station-filter'
import { TaxonFilter } from './filters/taxon-filter'
import { FilterProps } from './filters/types'

const ComponentMap: {
  [key: string]: (props: FilterProps) => JSX.Element
} = {
  classification_threshold: ScoreFilter,
  collection: CollectionFilter,
  deployment: StationFilter,
  detections__source_image: ImageFilter,
  event: SessionFilter,
  taxon: TaxonFilter,
}

interface FilterControlProps {
  clearable?: boolean
  field: string
  readonly?: boolean
}

export const FilterControl = ({
  clearable = true,
  field,
  readonly,
}: FilterControlProps) => {
  const { filters, addFilter, clearFilter } = useFilters()
  const label = AVAILABLE_FILTERS.find(
    (filter) => filter.field === field
  )?.label
  const value = filters.find((filter) => filter.field === field)?.value
  const FilterComponent = ComponentMap[field]

  if (!label) {
    return null
  }

  if (readonly && !value) {
    return null
  }

  return (
    <div>
      <label className="flex pl-2 pb-3 text-muted-foreground body-overline-small font-bold">
        {label}
      </label>
      <div className="flex items-center justify-between gap-2">
        <FilterComponent
          value={value}
          onAdd={(value) => addFilter(field, value)}
          onClear={() => clearFilter(field)}
        />
        {clearable && value && (
          <Button
            size="icon"
            className="shrink-0 text-muted-foreground"
            variant="ghost"
            onClick={() => clearFilter(field)}
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  )
}