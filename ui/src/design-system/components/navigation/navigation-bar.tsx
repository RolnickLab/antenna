import classNames from 'classnames'
import { useEffect, useState } from 'react'
import styles from './navigation-bar.module.scss'

interface NavigationBarProps {
  activeItemId: string
  items: { id: string; title: string; count?: number }[]
  onItemClick: (id: string) => void
}

export const NavigationBar = ({
  activeItemId,
  items,
  onItemClick,
}: NavigationBarProps) => {
  const [lineStyle, setLineStyle] = useState<React.CSSProperties>({})

  useEffect(() => {
    const element = activeItemId && document.getElementById(activeItemId)
    const updatedLineStyle = element
      ? {
          left: `${element.offsetLeft}px`,
          width: `${element.offsetWidth}px`,
        }
      : {}

    setLineStyle(updatedLineStyle)
  }, [activeItemId, items])

  return (
    <nav className={styles.wrapper}>
      <ul className={styles.items}>
        {items.map((item) => (
          <li key={item.id} id={item.id}>
            <div
              role="button"
              tabIndex={0}
              className={classNames(styles.item, {
                [styles.active]: activeItemId === item.id,
              })}
              onClick={() => onItemClick(item.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  onItemClick(item.id)
                }
              }}
            >
              <div className={styles.topContent}>
                {item.count !== undefined && (
                  <span className={styles.itemCount}>{item.count}</span>
                )}
              </div>
              <div>
                <span className={styles.itemTitle}>{item.title}</span>
              </div>
            </div>
          </li>
        ))}
        <div className={styles.line} style={lineStyle} />
      </ul>
    </nav>
  )
}
