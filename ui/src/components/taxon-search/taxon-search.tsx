import { Taxon } from 'data-services/models/taxa'
import { Command } from 'nova-ui-kit'
import { useMemo, useState } from 'react'
import { useDebounce } from 'utils/useDebounce'
import { buildTree } from './buildTree'
import { TreeItem } from './types'
import { useTaxonSearch } from './useTaxonSearch'

export const TaxonSearch = ({
  taxon,
  onTaxonChange,
}: {
  taxon?: Taxon
  onTaxonChange: (taxon?: Taxon) => void
}) => {
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data, isLoading } = useTaxonSearch(debouncedSearchString)

  const tree = useMemo(() => {
    if (!data?.length) {
      return []
    }

    return buildTree(
      data.map((taxon) => ({
        id: taxon.id,
        label: taxon.name,
        details: taxon.rank,
        parentId: taxon.parentId,
      }))
    )
  }, [data])

  return (
    <Command.Root shouldFilter={false}>
      <Command.Input
        loading={isLoading}
        placeholder="Search taxon..."
        value={searchString}
        onValueChange={setSearchString}
      />

      <Command.List>
        <Command.Empty>No results found.</Command.Empty>
        <Command.Group>
          {tree.map((treeItem) => (
            <CommandTreeItem
              key={treeItem.id}
              level={0}
              selectedId={taxon?.id}
              treeItem={treeItem}
              onSelect={(treeItem) => {
                const taxon = treeItem.id
                  ? data?.find((taxon) => taxon.id === treeItem.id)
                  : undefined

                onTaxonChange(taxon)
              }}
            />
          ))}
        </Command.Group>
      </Command.List>
    </Command.Root>
  )
}

const CommandTreeItem = ({
  level = 0,
  selectedId,
  treeItem,
  onSelect,
}: {
  level?: number
  selectedId?: string
  treeItem: TreeItem
  onSelect: (treeItem: TreeItem) => void
}) => (
  <>
    <Command.Item onSelect={() => onSelect(treeItem)}>
      <Command.Taxon
        hasChildren={treeItem.children.length > 0}
        label={treeItem.label}
        level={level}
        rank={treeItem.details ?? 'Unknown'}
        selected={treeItem.id === selectedId}
      />
    </Command.Item>
    {treeItem.children.map((child) => (
      <CommandTreeItem
        key={child.id}
        level={level + 1}
        selectedId={selectedId}
        treeItem={child}
        onSelect={onSelect}
      />
    ))}
  </>
)
