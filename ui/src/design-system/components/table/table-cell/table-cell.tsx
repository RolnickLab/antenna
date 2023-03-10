import styles from './table-cell.module.scss'

interface TableCellProps {
  title: string
  text: string[]
  children?: React.ReactNode
}

export const TableCell = ({ title, text = [], children }: TableCellProps) => {
  return (
    <td className={styles.container}>
      <span className={styles.title}>{title}</span>
      {text.map((content, index) => (
        <span key={index} className={styles.text}>
          {content}
        </span>
      ))}
      {children && <div className={styles.contentWrapper}>{children}</div>}
    </td>
  )
}
