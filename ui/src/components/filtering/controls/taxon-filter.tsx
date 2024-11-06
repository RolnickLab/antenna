import { TaxonSearch } from 'components/taxon-search/taxon-search'
import { useSpeciesDetails } from 'data-services/hooks/species/useSpeciesDetails'
import { ChevronDownIcon, Loader2 } from 'lucide-react'
import { Button, Popover } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useFilters } from 'utils/useFilters'

const FILTER_FIELD = 'taxon'

export const TaxonFilter = () => {
  const { projectId } = useParams()
  const [open, setOpen] = useState(false)
  const { filters, addFilter, clearFilter } = useFilters()
  const value = filters.find((filter) => filter.field === FILTER_FIELD)?.value
  const { species: taxon, isLoading } = useSpeciesDetails(value, projectId)

  const triggerLabel = (() => {
    if (taxon) {
      return taxon.name
    }
    if (value && isLoading) {
      return 'Loading...'
    }
    return 'All taxa'
  })()

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between text-muted-foreground font-normal"
        >
          <>
            <span>{triggerLabel}</span>
            {isLoading && value ? (
              <Loader2 className="h-4 w-4 ml-2 animate-spin" />
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
              addFilter(FILTER_FIELD, taxon?.id)
            } else {
              clearFilter(FILTER_FIELD)
            }
            setOpen(false)
          }}
        />
      </Popover.Content>
    </Popover.Root>
  )
}
