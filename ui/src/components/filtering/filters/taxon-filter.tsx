import { TaxonSearch } from 'components/taxon-search/taxon-search'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { ChevronDownIcon, Loader2Icon } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

export const TaxonFilter = ({ value, onAdd, onClear }: FilterProps) => {
  const { projectId } = useParams()
  const [open, setOpen] = useState(false)
  const { species: taxon, isLoading } = useSpeciesDetails(value, projectId)

  const triggerLabel = (() => {
    if (taxon) {
      return taxon.name
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return translate(STRING.SELECT_TAXON_PLACEHOLDER)
  })()

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between px-4 text-muted-foreground font-normal overflow-hidden"
        >
          <>
            <span className="overflow-hidden text-ellipsis">
              {triggerLabel}
            </span>
            {isLoading && value ? (
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
          onTaxonChange={(taxon) => {
            if (taxon) {
              onAdd(taxon.id)
            } else {
              onClear()
            }
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
