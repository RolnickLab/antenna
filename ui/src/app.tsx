import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { Header } from 'components/header/header'
import { Menu } from 'components/menu/menu'
import { Deployments } from 'pages/deployments/deployments'
import { Jobs } from 'pages/jobs/jobs'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Overview } from 'pages/overview/overview'
import { SessionDetails } from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Species } from 'pages/species/species'
import { UnderConstruction } from 'pages/under-construction/under-construction'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { BreadcrumbContextProvider } from 'utils/breadcrumbContext'
import styles from './app.module.scss'

const queryClient = new QueryClient()

export const App = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BreadcrumbContextProvider>
        <ReactQueryDevtools initialIsOpen={false} />
        <div className={styles.wrapper}>
          <Header />
          <Routes>
            <Route
              path="/"
              element={
                <Navigate
                  to={{
                    pathname: 'projects',
                    search: location.search,
                  }}
                  replace={true}
                />
              }
            />
            <Route path="login" element={<Login />} />
            <Route path="projects" element={<Projects />} />
            <Route path="projects/:projectId" element={<Project />}>
              <Route path="" element={<Overview />} />
              <Route path="jobs/:id?" element={<Jobs />} />
              <Route path="deployments/:id?" element={<Deployments />} />
              <Route path="sessions" element={<Sessions />} />
              <Route path="sessions/:id" element={<SessionDetails />} />
              <Route path="occurrences/:id?" element={<Occurrences />} />
              <Route path="species/:id?" element={<Species />} />
              <Route path="*" element={<UnderConstruction />} />
            </Route>
          </Routes>
        </div>
      </BreadcrumbContextProvider>
    </QueryClientProvider>
  )
}

const Login = () => {
  return (
    <>
      <main className={styles.main}>
        <div className={styles.content}>
          <UnderConstruction message="Login page is under construction!" />
        </div>
      </main>
    </>
  )
}

const Projects = () => {
  return (
    <>
      <main className={styles.main}>
        <div className={styles.content}>
          <UnderConstruction message="Project page is under construction!" />
        </div>
      </main>
    </>
  )
}

const Project = () => {
  return (
    <>
      <Menu />
      <main className={styles.main}>
        <div className={styles.content}>
          <Outlet />
        </div>
      </main>
    </>
  )
}
