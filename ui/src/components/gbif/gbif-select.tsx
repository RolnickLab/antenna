import { ChevronDownIcon, Loader2Icon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { GBIFSearch } from './gbif-search'
import { GBIFTaxon } from './types'

export const GBIFSelect = ({
  isLoading,
  onTaxonChange,
  rank,
  taxon,
  triggerLabel,
}: {
  isLoading?: boolean
  onTaxonChange: (taxon?: GBIFTaxon) => void
  rank?: string
  taxon?: GBIFTaxon
  triggerLabel: string
}) => {
  const [open, setOpen] = useState(false)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          aria-expanded={open}
          className="w-full justify-between px-4 text-muted-foreground font-normal"
          role="combobox"
          type="button"
          variant="outline"
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
        <GBIFSearch
          onTaxonChange={(taxon) => {
            onTaxonChange(taxon)
            setOpen(false)
          }}
          rank={rank}
          taxon={taxon}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
