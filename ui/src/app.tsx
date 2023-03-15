import { NavigationBar } from 'design-system/components/navigation/navigation-bar'
import { Deployments } from 'pages/deployments/deployments'
import { Occurrences } from 'pages/occurrences/occurrences'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import React from 'react'
import { Route, Routes, useNavigate } from 'react-router-dom'
import { useNavItems } from 'utils/useNavItems'
import styles from './app.module.scss'

export const App = () => {
  const navigate = useNavigate()
  const { navItems, activeNavItemId } = useNavItems()

  return (
    <>
      <header className={styles.header}></header>
      <div className={styles.page}>
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
        <main>
          <Routes>
            <Route path="/deployments" element={<Deployments />} />
            <Route path="/occurrences" element={<Occurrences />} />
            <Route path="*" element={<UnderConstruction />} />
          </Routes>
        </main>
      </div>
    </>
  )
}
