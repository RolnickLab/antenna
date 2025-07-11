import { Taxon } from 'data-services/models/taxa'
import { Command } from 'nova-ui-kit'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
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
  const { projectId } = useParams()
  const [searchString, setSearchString] = useState('')
  const debouncedSearchString = useDebounce(searchString, 200)
  const { data, isLoading } = useTaxonSearch(
    debouncedSearchString,
    projectId as string
  )

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
        image: taxon.image,
      }))
    )
  }, [data])

  return (
    <Command.Root
      shouldFilter={false}
      style={{
        maxHeight: 'calc(var(--radix-popover-content-available-height) - 2px)',
      }}
    >
      <Command.Input
        loading={isLoading}
        placeholder="Search taxa..."
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
    <Command.Item className="h-16 pr-2" onSelect={() => onSelect(treeItem)}>
      <Command.Taxon
        hasChildren={treeItem.children.length > 0}
        image={treeItem.image}
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
