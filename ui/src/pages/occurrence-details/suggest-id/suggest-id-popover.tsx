import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { SearchIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { SuggestId } from './suggest-id'

interface SuggestIdPopoverProps {
  occurrenceIds: string[]
}

export const SuggestIdPopover = ({ occurrenceIds }: SuggestIdPopoverProps) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <BasicTooltip asChild content={translate(STRING.SUGGEST_ID)}>
        <Popover.Trigger asChild>
          <Button size="icon" variant="outline">
            <SearchIcon className="w-4 h-4" />
          </Button>
        </Popover.Trigger>
      </BasicTooltip>
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
