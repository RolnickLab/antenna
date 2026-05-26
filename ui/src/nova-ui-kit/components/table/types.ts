export enum CellTheme {
  Default = 'default',
  Primary = 'primary',
  Bubble = 'bubble',
}

export { CarouselTheme as ImageCellTheme } from '../image-carousel/types'

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
  // Order applied when this field is first selected in the sort control. Useful
  // for date-like fields (e.g. "Recent ...") that read better newest-first.
  defaultSortOrder?: 'asc' | 'desc'
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
