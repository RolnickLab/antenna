import { BasicTableCell } from '../basic-table-cell/basic-table-cell'
import { CellTheme, OrderBy, TableColumn, TextAlign } from '../types'
import { Table } from './table'

interface Item {
  name: string
  numDetections: number
  numEvents: number
  numSourceImages: number
}

const items: Item[] = [
  {
    name: 'Newfoundland-Warren',
    numDetections: 23,
    numEvents: 1,
    numSourceImages: 1557,
  },
  {
    name: 'Panama',
    numDetections: 63,
    numEvents: 1,
    numSourceImages: 3,
  },
  {
    name: 'Vermont-Snapshots-Sample',
    numDetections: 172,
    numEvents: 5,
    numSourceImages: 178,
  },
]

const columns: TableColumn<Item>[] = [
  {
    id: 'deployment',
    field: 'name',
    name: 'Deployment',
    renderCell: (item: Item) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    field: 'numEvents',
    name: 'Sessions',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    field: 'numSourceImages',
    name: 'Images',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numSourceImages} />,
  },
  {
    id: 'detections',
    field: 'numDetections',
    name: 'Detections',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numDetections} />,
  },
]

const sortableColumns = columns.map((column) => ({
  ...column,
  sortable: true,
}))

export default {
  title: 'Components/Table/Table',
  component: Table,
  parameters: {
    backgrounds: {
      default: 'light',
    },
  },
  argTypes: {
    items: {
      control: { disable: true },
    },
    columns: {
      control: { disable: true },
    },
    defaultSortSettings: {
      control: { disable: true },
    },
  },
}

export const Basic = {
  args: {
    items,
    columns,
  },
}

export const Sortable = {
  args: {
    items,
    columns: sortableColumns,
    defaultSortSettings: {
      columnId: 'deployment',
      orderBy: OrderBy.Descending,
    },
  },
}
