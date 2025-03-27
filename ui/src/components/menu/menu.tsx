import { Breadcrumbs } from 'components/breadcrumbs/breadcrumbs'
import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { useNavigate } from 'react-router-dom'
import { useNavItems } from 'utils/useNavItems'
import styles from './menu.module.scss'

export const Menu = () => {
  const navigate = useNavigate()
  const { navItems, activeNavItem } = useNavItems()

  return (
    <div className={styles.menu}>
      <div className={styles.topBar}>
        <Breadcrumbs navItems={navItems} activeNavItem={activeNavItem} />
      </div>
      <div className={styles.navigationBar}>
        <NavigationBar
          items={navItems}
          activeItemId={activeNavItem.id}
          onItemClick={(id) => {
            const item = navItems.find((i) => i.id === id)
            if (item?.path) {
              navigate(item.path)
            }
          }}
        />
      </div>
    </div>
  )
}
