import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Header } from 'components/header/header'
import { BatchId } from 'pages/batch-id/batch-id'
import { Deployments } from 'pages/deployments/deployments'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Overview } from 'pages/overview/overview'
import { SessionDetails } from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Species } from 'pages/species/species'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import { Navigate, Route, Routes } from 'react-router-dom'
import { BreadcrumbContextProvider } from 'utils/breadcrumbContext'
import styles from './app.module.scss'

const queryClient = new QueryClient()

export const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ReactQueryDevtools initialIsOpen={false} />
      <BreadcrumbContextProvider>
        <div className={styles.wrapper}>
          <Header />
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
    </QueryClientProvider>
  )
}
