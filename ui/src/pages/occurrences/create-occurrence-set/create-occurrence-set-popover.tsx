import { API_ROUTES } from 'data-services/constants'
import { useEntities } from 'data-services/hooks/entities/useEntities'
import { BookmarkPlusIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { CreateOccurrenceSet } from './create-occurrence-set'

interface CreateOccurrenceSetPopoverProps {
  occurrenceIds: string[]
}

export const CreateOccurrenceSetPopover = ({
  occurrenceIds,
}: CreateOccurrenceSetPopoverProps) => {
  const { projectId } = useParams()
  const [open, setOpen] = useState(false)
  // The choices response also says whether the caller may create a set here.
  const { userPermissions } = useEntities(API_ROUTES.OCCURRENCE_SET_CHOICES, {
    projectId: projectId as string,
  })

  if (!userPermissions?.includes(UserPermission.Create)) {
    return null
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button size="small" variant="outline">
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
