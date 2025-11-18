import { XIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useFilters } from 'utils/useFilters'
import { AlgorithmFilter, NotAlgorithmFilter } from './filters/algorithm-filter'
import { BooleanFilter } from './filters/boolean-filter'
import { CollectionFilter } from './filters/collection-filter'
import { DateFilter } from './filters/date-filter'
import { ImageFilter } from './filters/image-filter'
import { PipelineFilter } from './filters/pipeline-filter'
import { SessionFilter } from './filters/session-filter'
import { StationFilter } from './filters/station-filter'
import { StatusFilter } from './filters/status-filter'
import { TagFilter } from './filters/tag-filter'
import { TaxaListFilter } from './filters/taxa-list-filter'
import { TaxonFilter } from './filters/taxon-filter'
import { TypeFilter } from './filters/type-filter'
import { FilterProps } from './filters/types'
import { VerificationStatusFilter } from './filters/verification-status-filter'
import { VerifiedByFilter } from './filters/verified-by-filter'

const ComponentMap: {
  [key: string]: (props: FilterProps) => JSX.Element
} = {
  algorithm: AlgorithmFilter,
  collection: CollectionFilter,
  collections: CollectionFilter,
  date_end: DateFilter,
  date_start: DateFilter,
  deployment: StationFilter,
  detections__source_image: ImageFilter,
  event: SessionFilter,
  include_unobserved: BooleanFilter,
  job_type_key: TypeFilter,
  not_algorithm: NotAlgorithmFilter,
  not_tag_id: TagFilter,
  not_taxa_list_id: TaxaListFilter,
  pipeline: PipelineFilter,
  source_image_collection: CollectionFilter,
  source_image_single: ImageFilter,
  status: StatusFilter,
  tag_id: TagFilter,
  taxa_list_id: TaxaListFilter,
  taxon: TaxonFilter,
  verified_by_me: VerifiedByFilter,
  verified: VerificationStatusFilter,
}

interface FilterControlProps {
  clearable?: boolean
  data?: any
  field: string
  readonly?: boolean
}

export const FilterControl = ({
  clearable = true,
  data,
  field,
  readonly,
}: FilterControlProps) => {
  const { filters, addFilter, clearFilter } = useFilters()
  const filter = filters.find((filter) => filter.field === field)
  const FilterComponent = ComponentMap[field]

  if (!filter || !FilterComponent) {
    return null
  }

  if (readonly && !filter?.value) {
    return null
  }

  return (
    <div>
      <label className="flex pl-2 pb-3 text-muted-foreground body-overline-small font-bold">
        {filter.label}
      </label>
      <div className="flex items-center justify-between gap-2">
        <FilterComponent
          data={data}
          error={filter.error}
          onAdd={(value) => addFilter(field, value)}
          onClear={() => clearFilter(field)}
          value={filter.value}
        />
        {clearable && filter.value && (
          <Button
            className="shrink-0 text-muted-foreground"
            onClick={() => clearFilter(field)}
            size="icon"
            variant="ghost"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        )}
      </div>
      {filter.error ? (
        <span className="flex pl-2 pt-3 body-small text-destructive italic">
          {filter.error}
        </span>
      ) : null}
    </div>
  )
}
