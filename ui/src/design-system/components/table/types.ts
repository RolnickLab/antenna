export enum CellTheme {
  Default = 'default',
  Primary = 'primary',
}

export enum ImageCellTheme {
  Default = 'default',
  Light = 'light',
}

export enum TextAlign {
  Left = 'left',
  Right = 'right',
}

export interface TableColumn<T> {
  id: string
  name: string
  sortField?: string
  styles?: {
    textAlign?: TextAlign
    padding?: string
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
