import { BREAKPOINTS } from 'components/constants'
import { ChevronsUpDown } from 'lucide-react'
import { Box, Button, Collapsible } from 'nova-ui-kit'
import { useFilters } from 'utils/useFilters'
import { FilterControl } from './filter-control'

interface FilteringProps {
  config: {
    algorithm?: boolean
    collection?: boolean
    station?: boolean
    verified?: boolean
    not_algorithm?: boolean
  }
}

export const AdvancedFiltering = ({ config }: FilteringProps) => {
  const { filters } = useFilters()

  // Set default open to true if any advanced filter is active
  const defaultOpen =
    window.innerWidth >= BREAKPOINTS.MD &&
    Object.entries(config).some(([field, active]) => {
      if (!active) {
        return false
      }

      return filters.find((filter) => filter.field === field)?.value
    })

  return (
    <Box className="w-full h-min shrink-0 p-2 rounded-lg md:w-72 md:p-4 md:rounded-xl">
      <Collapsible.Root className="space-y-4" defaultOpen={defaultOpen}>
        <div className="flex items-center justify-between ml-2">
          <span className="body-overline font-bold">Advanced filters</span>
          <Collapsible.Trigger asChild>
            <Button size="icon" variant="ghost">
              <ChevronsUpDown className="h-4 w-4" />
            </Button>
          </Collapsible.Trigger>
        </div>
        <Collapsible.Content className="space-y-6">
          {config.collection && <FilterControl field="collection" />}
          {config.station && <FilterControl field="deployment" />}
          {config.algorithm && <FilterControl field="algorithm" />}
          {config.not_algorithm && <FilterControl field="not_algorithm" />}
        </Collapsible.Content>
      </Collapsible.Root>
    </Box>
  )
}
