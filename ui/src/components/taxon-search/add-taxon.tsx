import { Taxon } from 'data-services/models/taxa'
import { PlusIcon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import { TaxonSearch } from './taxon-search'

export const AddTaxon = ({ onAdd }: { onAdd: (taxon?: Taxon) => void }) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between px-4 text-muted-foreground font-normal"
        >
          <>
            <span>
              {translate(STRING.ENTITY_ADD, {
                type: translate(STRING.ENTITY_TYPE_TAXON),
              })}
            </span>
            <PlusIcon className="h-4 w-4 ml-2" />
          </>
        </Button>
      </Popover.Trigger>
      <Popover.Content
        avoidCollisions={false}
        className="w-auto p-0 overflow-hidden"
        style={{ maxHeight: 'var(--radix-popover-content-available-height)' }}
      >
        <TaxonSearch
          onTaxonChange={(taxon) => {
            onAdd(taxon)
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
