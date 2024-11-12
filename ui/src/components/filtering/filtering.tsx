import { ChevronsUpDown } from 'lucide-react'
import { Box, Button, Collapsible } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { AVAILABLE_FILTERS, useFilters } from 'utils/useFilters'
import { CollectionFilter } from './controls/collection-filter'
import { ImageFilter } from './controls/image-filter'
import { ScoreFilter } from './controls/score-filter'
import { SessionFilter } from './controls/session-filter'
import { StationFilter } from './controls/station-filter'
import { TaxonFilter } from './controls/taxon-filter'

interface FilteringProps {
  config?: {
    capture?: boolean
    collection?: boolean
    scoreThreshold?: boolean
    session?: boolean
    station?: boolean
    taxon?: boolean
  }
}

export const Filtering = ({ config = {} }: FilteringProps) => (
  <Box className="w-full h-min shrink-0 rounded-lg md:rounded-xl md:w-72">
    <Collapsible.Root
      className="space-y-4"
      defaultOpen={window.innerWidth >= 768}
    >
      <div className="flex items-center justify-between ml-2">
        <span className="body-overline font-bold">Filters</span>
        <Collapsible.Trigger asChild>
          <Button size="icon" variant="ghost">
            <ChevronsUpDown className="h-4 w-4" />
          </Button>
        </Collapsible.Trigger>
      </div>
      <Collapsible.Content className="space-y-6">
        {config.capture && (
          <FilterControl field="detections__source_image" readonly>
            <ImageFilter />
          </FilterControl>
        )}
        {config.session && (
          <FilterControl field="event" readonly>
            <SessionFilter />
          </FilterControl>
        )}
        {config.collection && (
          <FilterControl field="collection">
            <CollectionFilter />
          </FilterControl>
        )}
        {config.station && (
          <FilterControl field="deployment">
            <StationFilter />
          </FilterControl>
        )}

        {config.taxon && (
          <FilterControl field="taxon">
            <TaxonFilter />
          </FilterControl>
        )}
        {config.scoreThreshold && (
          <FilterControl field="classification_threshold">
            <ScoreFilter />
          </FilterControl>
        )}
      </Collapsible.Content>
    </Collapsible.Root>
  </Box>
)

const FilterControl = ({
  field,
  readonly,
  children,
}: {
  field: string
  readonly?: boolean
  children?: ReactNode
}) => {
  const { filters } = useFilters()
  const label = AVAILABLE_FILTERS.find(
    (filter) => filter.field === field
  )?.label

  if (!label) {
    return null
  }

  if (readonly) {
    const value = filters.find((filter) => filter.field === field)?.value
    if (!value) {
      return null
    }
  }

  return (
    <div>
      <label className="flex pl-2 pb-3 text-muted-foreground body-overline-small font-bold">
        {label}
      </label>
      {children}
    </div>
  )
}
