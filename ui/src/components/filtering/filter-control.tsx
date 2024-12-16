import { X } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { AVAILABLE_FILTERS, useFilters } from 'utils/useFilters'
import { AlgorithmFilter, NotAlgorithmFilter } from './filters/algorithm-filter'
import { CollectionFilter } from './filters/collection-filter'
import { DateFilter } from './filters/date-filter'
import { ImageFilter } from './filters/image-filter'
import { PipelineFilter } from './filters/pipeline-filter'
import { ScoreFilter } from './filters/score-filter'
import { SessionFilter } from './filters/session-filter'
import { StationFilter } from './filters/station-filter'
import { StatusFilter } from './filters/status-filter'
import { TaxonFilter } from './filters/taxon-filter'
import { TypeFilter } from './filters/type-filter'
import { FilterProps } from './filters/types'
import { VerificationStatusFilter } from './filters/verification-status-filter'
import { VerifiedByFilter } from './filters/verified-by-filter'

const ComponentMap: {
  [key: string]: (props: FilterProps) => JSX.Element
} = {
  algorithm: AlgorithmFilter,
  classification_threshold: ScoreFilter,
  collection: CollectionFilter,
  date_end: DateFilter,
  date_start: DateFilter,
  deployment: StationFilter,
  detections__source_image: ImageFilter,
  event: SessionFilter,
  job_type_key: TypeFilter,
  not_algorithm: NotAlgorithmFilter,
  pipeline: PipelineFilter,
  source_image_collection: CollectionFilter,
  source_image_single: ImageFilter,
  status: StatusFilter,
  taxon: TaxonFilter,
  verified_by_me: VerifiedByFilter,
  verified: VerificationStatusFilter,
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

  if (!label || !FilterComponent) {
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
