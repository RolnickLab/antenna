import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { PlusIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { AddTaxaListTaxon } from './add-taxa-list-taxon'

export const AddTaxaListTaxonPopover = ({
  compact,
  taxaListId,
}: {
  compact?: boolean
  taxaListId: string
}) => {
  const [open, setOpen] = useState(false)
  const buttonLabel = translate(STRING.ENTITY_ADD, {
    type: translate(STRING.ENTITY_TYPE_TAXON),
  })

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      {compact ? (
        <BasicTooltip asChild content={buttonLabel}>
          <Popover.Trigger asChild>
            <Button aria-label={buttonLabel} size="icon" variant="ghost">
              <PlusIcon className="w-4 h-4" />
            </Button>
          </Popover.Trigger>
        </BasicTooltip>
      ) : (
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>
            {translate(STRING.ENTITY_ADD, {
              type: translate(STRING.ENTITY_TYPE_TAXON),
            })}
          </span>
        </Button>
      )}
      <Popover.Portal>
        <Popover.Content align="end" className="p-0 w-72">
          <AddTaxaListTaxon
            onCancel={() => setOpen(false)}
            taxaListId={taxaListId}
          />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
