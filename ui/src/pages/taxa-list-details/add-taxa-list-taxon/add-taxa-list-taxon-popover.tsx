import { PlusIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { AddTaxaListTaxon } from './add-taxa-list-taxon'

export const AddTaxaListTaxonPopover = ({
  taxaListId,
}: {
  taxaListId: string
}) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>
            {translate(STRING.ENTITY_ADD, {
              type: translate(STRING.ENTITY_TYPE_TAXON),
            })}
          </span>
        </Button>
      </Popover.Trigger>
      <Popover.Content align="end" className="p-0 w-72">
        <AddTaxaListTaxon
          onCancel={() => setOpen(false)}
          taxaListId={taxaListId}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
