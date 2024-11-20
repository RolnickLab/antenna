import { BREAKPOINTS } from 'components/constants'
import { ChevronsUpDown } from 'lucide-react'
import { Box, Button, Collapsible } from 'nova-ui-kit'
import { ReactNode } from 'react'

interface FilteringProps {
  children?: ReactNode
}

export const Filtering = ({ children }: FilteringProps) => (
  <Box className="w-full h-min shrink-0 p-2 rounded-lg md:w-72 md:p-4 md:rounded-xl">
    <Collapsible.Root
      className="space-y-4"
      defaultOpen={window.innerWidth >= BREAKPOINTS.MD}
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
        {children}
      </Collapsible.Content>
    </Collapsible.Root>
  </Box>
)
