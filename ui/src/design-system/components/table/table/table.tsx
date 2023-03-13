import { TableColumn } from '../types'
import styles from './table.module.scss'

interface TableProps<T> {
  items: T[]
  columns: TableColumn<T>[]
}

export const Table = <T,>({ items, columns }: TableProps<T>) => {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column.id} style={{ textAlign: column.textAlign }}>
              <span>{column.name}</span>
            </th>
          ))}
          <th aria-hidden="true" className={styles.fill} />
        </tr>
      </thead>
      <tbody>
        {items.map((item, index) => (
          <tr key={index}>
            {columns.map((column, index) => (
              <td key={index}>{column.renderCell(item)}</td>
            ))}
            <td aria-hidden="true" />
          </tr>
        ))}
      </tbody>
    </table>
  )
}
