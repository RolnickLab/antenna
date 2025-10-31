import { Command } from 'nova-ui-kit'
import { useState } from 'react'
import { useDebounce } from 'utils/useDebounce'
import { GBIFTaxon } from './types'
import { useGBIFSearch } from './useGBIFSearch'

export const GBIFSearch = ({
  onTaxonChange,
  rank,
  taxon,
}: {
  onTaxonChange: (taxon?: GBIFTaxon) => void
  rank?: string
  taxon?: GBIFTaxon
}) => {
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data, isLoading } = useGBIFSearch({
    searchString: debouncedSearchString,
    rank,
  })

  return (
    <Command.Root
      shouldFilter={false}
      style={{
        maxHeight: 'calc(var(--radix-popover-content-available-height) - 2px)',
      }}
    >
      <Command.Input
        loading={isLoading}
        placeholder="Search GBIF..."
        value={searchString}
        onValueChange={setSearchString}
      />
      <Command.List>
        <Command.Empty>No results found.</Command.Empty>
        <Command.Group>
          {data?.map((t) => (
            <Command.Item
              key={t.key}
              className="h-16 pr-2"
              onSelect={() => onTaxonChange(t)}
            >
              <Command.Taxon
                label={t.canonicalName}
                rank={t.rank}
                selected={t.key === taxon?.key}
              />
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Root>
  )
}
