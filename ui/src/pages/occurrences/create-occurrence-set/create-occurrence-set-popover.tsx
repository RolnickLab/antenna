import { BookmarkPlusIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
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
      <Popover.Trigger asChild>
        <Button
          aria-label={translate(STRING.CREATE_OCCURRENCE_SET)}
          size="small"
          variant="outline"
        >
          <BookmarkPlusIcon className="w-4 h-4" />
          <span>{translate(STRING.CREATE_SET)}</span>
        </Button>
      </Popover.Trigger>
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
