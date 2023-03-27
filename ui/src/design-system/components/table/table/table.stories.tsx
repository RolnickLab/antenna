import { BasicTableCell } from '../basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn, TextAlign } from '../types'
import { Table } from './table'

interface Item {
  name: string
  numDetections: number
  numEvents: number
  numImages: number
}

const items: Item[] = [
  {
    name: 'Newfoundland-Warren',
    numDetections: 23,
    numEvents: 1,
    numImages: 1557,
  },
  {
    name: 'Panama',
    numDetections: 63,
    numEvents: 1,
    numImages: 3,
  },
  {
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
    renderCell: (item: Item) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    name: 'Sessions',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Item) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    name: 'Images',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Item) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    name: 'Detections',
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

export const Default = {
  args: {
    items,
    columns,
  },
}
