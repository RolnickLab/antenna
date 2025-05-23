import { Taxon } from 'data-services/models/taxa'
import { ChevronDownIcon, Loader2Icon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { TaxonSearch } from './taxon-search'

export const TaxonSelect = ({
  isLoading,
  onTaxonChange,
  taxon,
  triggerLabel,
  projectId,
}: {
  isLoading?: boolean
  onTaxonChange: (taxon?: Taxon) => void
  taxon?: Taxon
  triggerLabel: string
  projectId?: string
}) => {
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
            <span>{triggerLabel}</span>
            {isLoading ? (
              <Loader2Icon className="h-4 w-4 ml-2 animate-spin" />
            ) : (
              <ChevronDownIcon className="h-4 w-4 ml-2" />
            )}
          </>
        </Button>
      </Popover.Trigger>
      <Popover.Content
        avoidCollisions={false}
        className="w-auto p-0 overflow-hidden"
        style={{ maxHeight: 'var(--radix-popover-content-available-height)' }}
      >
        <TaxonSearch
          taxon={taxon}
          projectId={projectId}
          onTaxonChange={(taxon) => {
            onTaxonChange(taxon)
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
