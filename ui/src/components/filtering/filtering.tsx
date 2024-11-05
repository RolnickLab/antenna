import { Box } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { CollectionFilter } from './controls/collection-filter'

interface FilteringProps {
  config?: {
    collection?: boolean
  }
}

export const Filtering = ({ config = {} }: FilteringProps) => (
  <Box className="w-72 h-min shrink-0 sticky top-6 space-y-4" label="Filters">
    <div className="space-y-6">
      {config.collection && (
        <FilterControl label="Collection">
          <CollectionFilter />
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
