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
  renderCell: (item: T, rowIndex: number, columnIndex: number) => JSX.Element
  sortField?: string
  sticky?: boolean
  styles?: {
    textAlign?: TextAlign
    padding?: string
    width?: string | number
  }
  tooltip?: string
  visuallyHidden?: boolean
}

// TODO: This type is no longer used for tables only and should be extracted
export interface TableSortSettings {
  field: string
  order: 'asc' | 'desc'
}
