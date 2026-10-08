import { BookmarkPlusIcon } from 'lucide-react'
import { BasicTooltip, Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { CreateOccurrenceSet } from './create-occurrence-set'

interface CreateOccurrenceSetPopoverProps {
  occurrenceIds: string[]
}

export const CreateOccurrenceSetPopover = ({
  occurrenceIds,
}: CreateOccurrenceSetPopoverProps) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <BasicTooltip asChild content={translate(STRING.CREATE_OCCURRENCE_SET)}>
        <Popover.Trigger asChild>
          <Button
            aria-label={translate(STRING.CREATE_OCCURRENCE_SET)}
            size="icon"
            variant="outline"
          >
            <BookmarkPlusIcon className="w-4 h-4" />
          </Button>
        </Popover.Trigger>
      </BasicTooltip>
      <Popover.Content
        className="p-0 w-72"
        style={{ maxHeight: 'var(--radix-popover-content-available-height)' }}
      >
        <CreateOccurrenceSet
          occurrenceIds={occurrenceIds}
          onCancel={() => setOpen(false)}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
