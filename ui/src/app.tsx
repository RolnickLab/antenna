import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { BatchId } from 'pages/batch-id/batch-id'
import { Deployments } from 'pages/deployments/deployments'
import { Occurrences } from 'pages/occurrences/occurrences'
import { SessionDetails } from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Settings } from 'pages/settings/settings'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import { useContext, useEffect } from 'react'
import { Link, Route, Routes, useNavigate } from 'react-router-dom'
import {
  Breadcrumb,
  BreadcrumbContext,
  BreadcrumbContextProvider,
} from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import { useNavItems } from 'utils/useNavItems'
import styles from './app.module.scss'

export const App = () => {
  const navigate = useNavigate()
  const { navItems, activeNavItemId } = useNavItems()

  return (
    <BreadcrumbContextProvider>
      <div className={styles.wrapper}>
        <header className={styles.header}>
          <div className={styles.topBar}>
            <Breadcrumbs
              navItems={navItems}
              activeNavItemId={activeNavItemId}
            />
            <Settings />
          </div>
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
        </header>
        <main className={styles.content}>
          <Routes>
            <Route path="/batch-id" element={<BatchId />} />
            <Route path="/deployments" element={<Deployments />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/sessions/:id" element={<SessionDetails />} />
            <Route path="/occurrences" element={<Occurrences />} />

            {/* Work in progress pages */}
            <Route
              path="/overview"
              element={
                <UnderConstruction message="Overview is under construction!" />
              }
            />
            <Route
              path="/species"
              element={
                <UnderConstruction message="Species is under construction!" />
              }
            />
            <Route
              path="/deployments/:id"
              element={
                <UnderConstruction message="Deployment details is under construction!" />
              }
            />

            <Route
              path="/occurrences/:id"
              element={
                <UnderConstruction message="Occurrence details is under construction!" />
              }
            />
            <Route path="*" element={<UnderConstruction />} />
          </Routes>
        </main>
      </div>
    </BreadcrumbContextProvider>
  )
}

const Breadcrumbs = ({
  navItems,
  activeNavItemId,
}: {
  navItems: { id: string; title: string; path: string }[]
  activeNavItemId: string
}) => {
  const { mainBreadcrumb, detailBreadcrumb, setMainBreadcrumb } =
    useContext(BreadcrumbContext)

  useEffect(() => {
    const activeNavItem =
      activeNavItemId !== 'overview' &&
      navItems.find((navItem) => navItem.id === activeNavItemId)

    setMainBreadcrumb(
      activeNavItem
        ? { title: activeNavItem.title, path: activeNavItem.path }
        : undefined
    )
  }, [navItems, activeNavItemId])

  const breadcrumbs = [
    { title: translate(STRING.NAV_ITEM_PROJECT), path: '/' },
    mainBreadcrumb,
    detailBreadcrumb,
  ].filter((breadcrumb) => !!breadcrumb) as Breadcrumb[]

  return (
    <div className={styles.breadcrumbs}>
      {breadcrumbs.map((breadcrumb, index) => {
        if (index === breadcrumbs.length - 1) {
          return <span className={styles.breadcrumb}>{breadcrumb.title}</span>
        }
        return (
          <>
            <Link
              key={index}
              to={breadcrumb.path}
              className={classNames(styles.breadcrumb, styles.link)}
            >
              <span>{breadcrumb.title}</span>
            </Link>
            <Icon
              type={IconType.ToggleRight}
              theme={IconTheme.Neutral}
              size={8}
            />
          </>
        )
      })}
    </div>
  )
}
