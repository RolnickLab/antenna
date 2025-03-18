import * as Portal from '@radix-ui/react-portal'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import classNames from 'classnames'
import { Analytics } from 'components/analytics'
import { CookieDialog } from 'components/cookie-dialog/cookie-dialog'
import { ErrorBoundary } from 'components/error-boundary/error-boundary'
import { Header } from 'components/header/header'
import { CodeOfConductPage } from 'components/info-page/code-of-conduct-page/code-of-conduct-page'
import { TermsOfServicePage } from 'components/info-page/terms-of-service-page/terms-of-service-page'
import { Menu } from 'components/menu/menu'
import { TermsOfServiceInfo } from 'components/terms-of-service-info/terms-of-service-info'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { AlertCircleIcon, ChevronRightIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { Auth } from 'pages/auth/auth'
import { Login } from 'pages/auth/login'
import { ResetPassword } from 'pages/auth/reset-password'
import { ResetPasswordConfirm } from 'pages/auth/reset-password-confirm'
import { CollectionDetails } from 'pages/collection-details/collection-details'
import { Deployments } from 'pages/deployments/deployments'
import { Jobs } from 'pages/jobs/jobs'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Collections } from 'pages/overview/collections/collections'
import { Devices } from 'pages/overview/entities/devices'
import { Sites } from 'pages/overview/entities/sites'
import Overview from 'pages/overview/overview'
import { Pipelines } from 'pages/overview/pipelines/pipelines'
import { ProcessingServices } from 'pages/overview/processing-services/processing-services'
import { Storage } from 'pages/overview/storage/storage'
import { Summary } from 'pages/overview/summary/summary'
import { Projects } from 'pages/projects/projects'
import SessionDetails from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Species } from 'pages/species/species'
import { ReactNode, useContext, useEffect } from 'react'
import { Helmet, HelmetProvider } from 'react-helmet-async'
import {
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useParams,
} from 'react-router-dom'
import {
  BreadcrumbContext,
  BreadcrumbContextProvider,
} from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { CookieConsentContextProvider } from 'utils/cookieConsent/cookieConsentContext'
import { STRING, translate } from 'utils/language'
import { usePageBreadcrumb } from 'utils/usePageBreadcrumb'
import { DEFAULT_PAGE_TITLE } from 'utils/usePageTitle'
import { UserContextProvider } from 'utils/user/userContext'
import { UserInfoContextProvider } from 'utils/user/userInfoContext'
import { UserPreferencesContextProvider } from 'utils/userPreferences/userPreferencesContext'
import styles from './app.module.scss'

const queryClient = new QueryClient()
const APP_CONTAINER_ID = 'app'
const INTRO_CONTAINER_ID = 'intro'

export const App = () => (
  <AppProviders>
    <Helmet>
      <title>{DEFAULT_PAGE_TITLE}</title>
      <meta
        name="description"
        content="An interdisciplinary platform to upload, classify, and analyse in-the-wild images of invertebrates for research and conservation efforts."
      />
    </Helmet>
    <div id={APP_CONTAINER_ID} className={styles.wrapper}>
      <div id={INTRO_CONTAINER_ID}>
        <Header />
      </div>
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
        <Route path="auth" element={<AuthContainer />}>
          <Route path="login" element={<Login />} />
          <Route path="reset-password" element={<ResetPassword />} />
          <Route
            path="reset-password-confirm"
            element={<ResetPasswordConfirm />}
          />
        </Route>
        <Route path="projects" element={<ProjectsContainer />} />
        <Route path="projects/:projectId" element={<ProjectContainer />}>
          <Route path="" element={<Overview />}>
            <Route
              path=""
              element={<Navigate to={{ pathname: 'summary' }} replace={true} />}
            />
            <Route path="summary" element={<Summary />} />
            <Route path="collections" element={<Collections />} />
            <Route path="collections/:id" element={<CollectionDetails />} />
            <Route
              path="processing-services"
              element={<ProcessingServices />}
            />
            <Route path="pipelines" element={<Pipelines />} />
            <Route path="sites" element={<Sites />} />
            <Route path="devices" element={<Devices />} />
            <Route path="storage" element={<Storage />} />
          </Route>
          <Route path="jobs/:id?" element={<Jobs />} />
          <Route path="deployments/:id?" element={<Deployments />} />
          <Route path="sessions" element={<Sessions />} />
          <Route path="sessions/:id" element={<SessionDetails />} />
          <Route path="occurrences/:id?" element={<Occurrences />} />
          <Route path="taxa/:id?" element={<Species />} />
        </Route>
        <Route
          path="/terms-of-service"
          element={
            <InfoPageContainer>
              <TermsOfServicePage />
            </InfoPageContainer>
          }
        />
        <Route
          path="/code-of-conduct"
          element={
            <InfoPageContainer>
              <CodeOfConductPage />
            </InfoPageContainer>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
    <ReactQueryDevtools initialIsOpen={false} />
    <CookieDialog />
    <Analytics />
  </AppProviders>
)

const AppProviders = ({ children }: { children: ReactNode }) => (
  <HelmetProvider>
    <QueryClientProvider client={queryClient}>
      <CookieConsentContextProvider>
        <UserPreferencesContextProvider>
          <UserContextProvider>
            <UserInfoContextProvider>
              <BreadcrumbContextProvider>{children}</BreadcrumbContextProvider>
            </UserInfoContextProvider>
          </UserContextProvider>
        </UserPreferencesContextProvider>
      </CookieConsentContextProvider>
    </QueryClientProvider>
  </HelmetProvider>
)

const AuthContainer = () => (
  <main className={classNames(styles.main, styles.fullscreen)}>
    <Auth>
      <ErrorBoundary>
        <Outlet />
      </ErrorBoundary>
    </Auth>
  </main>
)

const ProjectsContainer = () => {
  usePageBreadcrumb({
    title: translate(STRING.NAV_ITEM_PROJECTS),
    path: APP_ROUTES.HOME,
  })

  return (
    <main className={styles.main}>
      <TermsOfServiceInfo />
      <div className={styles.content}>
        <ErrorBoundary>
          <Projects />
        </ErrorBoundary>
      </div>
    </main>
  )
}

const ProjectContainer = () => {
  const { projectId } = useParams()
  const projectDetails = useProjectDetails(projectId as string)
  const { setProjectBreadcrumb } = useContext(BreadcrumbContext)

  usePageBreadcrumb({
    title: translate(STRING.NAV_ITEM_PROJECTS),
    path: APP_ROUTES.HOME,
  })

  useEffect(() => {
    setProjectBreadcrumb({
      title: projectDetails.project?.name ?? '',
      path: APP_ROUTES.PROJECT_DETAILS({ projectId: projectId as string }),
    })

    return () => {
      setProjectBreadcrumb(undefined)
    }
  }, [projectDetails.project])

  return (
    <>
      <Helmet>
        <meta
          name="description"
          content={projectDetails.project?.description}
        />
      </Helmet>
      <Portal.Root container={document.getElementById(INTRO_CONTAINER_ID)}>
        <Menu />
      </Portal.Root>
      <main className={styles.main}>
        <div className={styles.content}>
          <ErrorBoundary>
            <Outlet context={projectDetails} />
          </ErrorBoundary>
        </div>
      </main>
    </>
  )
}

const InfoPageContainer = ({ children }: { children: ReactNode }) => (
  <main className={styles.main}>
    <div className={styles.content}>
      <ErrorBoundary>{children}</ErrorBoundary>
    </div>
  </main>
)

const NotFound = () => (
  <>
    <Helmet>
      <title>Page not found | {DEFAULT_PAGE_TITLE}</title>
    </Helmet>
    <main className={styles.main}>
      <div className={styles.content}>
        <div className="flex flex-col items-center py-24">
          <AlertCircleIcon className="w-8 h-8 text-destructive mb-8" />
          <span className="body-large font-medium mb-2">Page not found</span>
          <span className="body-base text-muted-foreground mb-8">
            Sorry, we couldn't find the page you are looking for.
          </span>
          <Link
            to={APP_ROUTES.HOME}
            className={buttonVariants({ variant: 'link' })}
          >
            <span>To homepage</span>
            <ChevronRightIcon className="w-4 h-4 ml-2" />
          </Link>
        </div>
      </div>
    </main>
  </>
)
