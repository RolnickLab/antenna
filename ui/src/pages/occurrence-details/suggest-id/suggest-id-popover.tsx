import { SearchIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { SuggestId } from './suggest-id'

interface SuggestIdPopoverProps {
  occurrenceIds: string[]
}

export const SuggestIdPopover = ({ occurrenceIds }: SuggestIdPopoverProps) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button size="icon" variant="outline">
          <SearchIcon className="w-4 h-4" />
        </Button>
      </Popover.Trigger>
      <Popover.Content
        className="p-0 w-72"
        style={{ maxHeight: 'var(--radix-popover-content-available-height)' }}
      >
        <SuggestId
          occurrenceIds={occurrenceIds}
          onCancel={() => setOpen(false)}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
