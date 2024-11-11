import { Box } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { CollectionFilter } from './controls/collection-filter'
import { ScoreFilter } from './controls/score-filter'
import { SessionFilter } from './controls/session-filter'
import { StationFilter } from './controls/station-filter'
import { TaxonFilter } from './controls/taxon-filter'

interface FilteringProps {
  config?: {
    collection?: boolean
    scoreThreshold?: boolean
    session?: boolean
    station?: boolean
    taxon?: boolean
  }
}

export const Filtering = ({ config = {} }: FilteringProps) => (
  <Box className="w-72 h-min shrink-0 space-y-4" label="Filters">
    <div className="space-y-6">
      {config.collection && (
        <FilterControl label="Collection">
          <CollectionFilter />
        </FilterControl>
      )}
      {config.station && (
        <FilterControl label="Station">
          <StationFilter />
        </FilterControl>
      )}
      {config.session && (
        <FilterControl label="Session">
          <SessionFilter />
        </FilterControl>
      )}
      {config.taxon && (
        <FilterControl label="Taxon">
          <TaxonFilter />
        </FilterControl>
      )}
      {config.scoreThreshold && (
        <FilterControl label="Score threshold">
          <ScoreFilter />
        </FilterControl>
      )}
    </div>
  </Box>
)

const FilterControl = ({
  label,
  children,
}: {
  label: string
  children?: ReactNode
}) => (
  <div>
    <label className="flex pl-2 pb-3 text-muted-foreground body-overline-small font-bold">
      {label}
    </label>
    {children}
  </div>
)
