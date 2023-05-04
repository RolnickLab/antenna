import { Breadcrumbs } from 'components/breadcrumbs'
import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { BatchId } from 'pages/batch-id/batch-id'
import { Deployments } from 'pages/deployments/deployments'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Overview } from 'pages/overview/overview'
import { SessionDetails } from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Settings } from 'pages/settings/settings'
import { Species } from 'pages/species/species'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { BreadcrumbContextProvider } from 'utils/breadcrumbContext'
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
            <Route path="/" element={<Navigate to="/overview" />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/batch-id" element={<BatchId />} />
            <Route path="/deployments" element={<Deployments />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/sessions/:id" element={<SessionDetails />} />
            <Route path="/occurrences/:id?" element={<Occurrences />} />
            <Route path="/occurrences" element={<Occurrences />} />
            <Route path="/species" element={<Species />} />

            {/* Work in progress pages */}
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
            <Route
              path="/species/:id"
              element={
                <UnderConstruction message="Species details is under construction!" />
              }
            />
            <Route path="*" element={<UnderConstruction />} />
          </Routes>
        </main>
      </div>
    </BreadcrumbContextProvider>
  )
}
