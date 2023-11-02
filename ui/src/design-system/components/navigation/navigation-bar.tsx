import classNames from 'classnames'
import { useEffect, useState } from 'react'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './navigation-bar.module.scss'

interface NavigationBarProps {
  activeItemId: string
  items: {
    count?: number
    icon?: IconType
    id: string
    path?: string
    title: string
  }[]
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
        {items
          .filter((item) => item.path)
          .map((item) => {
            const isActive = activeItemId === item.id

            return (
              <li key={item.id} id={item.id}>
                <div
                  role="button"
                  tabIndex={0}
                  className={classNames(styles.item, {
                    [styles.active]: isActive,
                  })}
                  onClick={() => onItemClick(item.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      onItemClick(item.id)
                    }
                  }}
                >
                  <div className={styles.topContent}>
                    {item.icon && (
                      <Icon
                        type={item.icon}
                        theme={isActive ? IconTheme.Success : IconTheme.Primary}
                      />
                    )}
                    {item.count !== undefined && (
                      <span className={styles.itemCount}>{item.count}</span>
                    )}
                  </div>
                  <span className={styles.itemTitle}>{item.title}</span>
                </div>
              </li>
            )
          })}
        <div className={styles.line} style={lineStyle} />
      </ul>
    </nav>
  )
}
