import { Breadcrumbs } from 'components/breadcrumbs/breadcrumbs'
import { InfoDialog } from 'components/info-dialog/info-dialog'
import { usePages } from 'data-services/hooks/pages/usePages'
import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { Link, useNavigate } from 'react-router-dom'
import { useNavItems } from 'utils/useNavItems'
import ami from './ami.png'
import styles from './header.module.scss'

export const Header = () => {
  const navigate = useNavigate()
  const { navItems, activeNavItemId } = useNavItems()
  const { pages = [] } = usePages()

  return (
    <header className={styles.header}>
      <div className={styles.logoBar}>
        <Link to="/">
          <img src={ami} alt="AMI" width={40} height={36} />
        </Link>
        <div className={styles.infoPages}>
          {pages.map((page) => (
            <InfoDialog key={page.id} name={page.name} slug={page.slug} />
          ))}
        </div>
      </div>
      <div className={styles.topBar}>
        <Breadcrumbs navItems={navItems} activeNavItemId={activeNavItemId} />
      </div>
      <div className={styles.navigationBar}>
        <NavigationBar
          items={navItems}
          activeItemId={activeNavItemId}
          onItemClick={(id) => {
            const item = navItems.find((i) => i.id === id)
            if (item) {
              navigate(item.path)
            }
          }}
        />
      </div>
    </header>
  )
}
