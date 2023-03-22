import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { BatchId } from 'pages/batch-id/batch-id'
import { Deployments } from 'pages/deployments/deployments'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Sessions } from 'pages/sessions/sessions'
import { Settings } from 'pages/settings/settings'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import React from 'react'
import { Route, Routes, useNavigate } from 'react-router-dom'
import { useNavItems } from 'utils/useNavItems'
import styles from './app.module.scss'

export const App = () => {
  const navigate = useNavigate()
  const { navItems, activeNavItemId } = useNavItems()

  return (
    <div className={styles.wrapper}>
      <header className={styles.header}>
        <div className={styles.topBar}>
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
      <div className={styles.page}>
        <main className={styles.content}>
          <Routes>
            <Route path="/batch-id" element={<BatchId />} />
            <Route path="/deployments" element={<Deployments />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/occurrences" element={<Occurrences />} />
            <Route path="*" element={<UnderConstruction />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
