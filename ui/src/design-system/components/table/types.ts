export enum CellTheme {
  Default = 'default',
  Primary = 'primary',
}

export enum TextAlign {
  Left = 'left',
  Right = 'right',
}

export interface TableColumn<T> {
  id: string
  name: string
  textAlign?: TextAlign
  renderCell: (item: T) => JSX.Element
}
