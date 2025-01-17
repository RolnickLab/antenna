export { CarouselTheme as ImageCellTheme } from '../image-carousel/types'

export enum CellTheme {
  Default = 'default',
  Primary = 'primary',
  Bubble = 'bubble',
}

export enum TextAlign {
  Left = 'left',
  Right = 'right',
  Center = 'center',
}

export interface TableColumn<T> {
  id: string
  name: string
  tooltip?: string
  sortField?: string
  styles?: {
    textAlign?: TextAlign
    padding?: string
    width?: string | number
  }
  visuallyHidden?: boolean
  renderCell: (item: T, rowIndex: number, columnIndex: number) => JSX.Element
}

export interface TableSortSettings {
  field: string
  order: 'asc' | 'desc'
}

export interface TablePaginationSettings {
  page: number
  perPage: number
}
