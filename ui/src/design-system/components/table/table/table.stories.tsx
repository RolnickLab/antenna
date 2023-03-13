import { BasicTableCell } from '../basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn, TextAlign } from '../types'
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
    name: 'Deployment',
    renderCell: (item: Item) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    name: 'Sessions',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    name: 'Images',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numSourceImages} />,
  },
  {
    id: 'detections',
    name: 'Detections',
    textAlign: TextAlign.Right,
    renderCell: (item: Item) => <BasicTableCell value={item.numDetections} />,
  },
]

export default {
  title: 'Components/Table/Table',
  component: Table,
}

export const Basic = {
  args: {
    items,
    columns,
  },
}
