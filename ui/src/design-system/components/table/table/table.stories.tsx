import { ComponentStory } from '@storybook/react'
import _ from 'lodash'
import { useEffect, useState } from 'react'
import { BasicTableCell } from '../basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn, TableSortSettings, TextAlign } from '../types'
import { Table } from './table'

interface Item {
  id: string
  name: string
  numDetections: number
  numEvents: number
  numImages: number
}

const items: Item[] = [
  {
    id: 'item-01',
    name: 'Newfoundland-Warren',
    numDetections: 23,
    numEvents: 1,
    numImages: 1557,
  },
  {
    id: 'item-02',
    name: 'Panama',
    numDetections: 63,
    numEvents: 1,
    numImages: 3,
  },
  {
    id: 'item-03',
    name: 'Vermont-Snapshots-Sample',
    numDetections: 172,
    numEvents: 5,
    numImages: 178,
  },
]

const columns: TableColumn<Item>[] = [
  {
    id: 'deployment',
    name: 'Deployment',
    sortField: 'name',
    renderCell: (item: Item) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    name: 'Sessions',
    sortField: 'numEvents',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Item) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    name: 'Images',
    sortField: 'numImages',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Item) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    name: 'Detections',
    sortField: 'numDetections',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Item) => <BasicTableCell value={item.numDetections} />,
  },
]

export default {
  title: 'Components/Table/Table',
  component: Table,
  parameters: {
    backgrounds: {
      default: 'light',
    },
  },
}

const DefaultTemplate: ComponentStory<typeof Table> = () => (
  <Table items={items} columns={columns} />
)

const LoadingTemplate: ComponentStory<typeof Table> = () => (
  <Table items={items} columns={columns} isLoading={true} />
)

const EmptyLoadingTemplate: ComponentStory<typeof Table> = () => (
  <Table items={[]} columns={columns} isLoading={true} />
)

const SortableTableTemplate: ComponentStory<typeof Table> = () => {
  const [sortedItems, setSortedItems] = useState(items)
  const [sort, setSort] = useState<TableSortSettings | undefined>()

  useEffect(() => {
    if (sort) {
      setSortedItems(_.orderBy(items, sort.field, sort.order))
    } else {
      setSortedItems(items)
    }
  }, [items, sort])

  return (
    <Table
      items={sortedItems}
      columns={columns}
      sortable
      sortSettings={sort}
      onSortSettingsChange={setSort}
    />
  )
}

export const Default = DefaultTemplate.bind({})
export const Loading = LoadingTemplate.bind({})
export const EmptyLoading = EmptyLoadingTemplate.bind({})
export const Sortable = SortableTableTemplate.bind({})
