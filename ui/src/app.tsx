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
import { Captures } from 'pages/captures/captures'
import { Deployments } from 'pages/deployments/deployments'
import { Jobs } from 'pages/jobs/jobs'
import { Occurrences } from 'pages/occurrences/occurrences'
import { Algorithms } from 'pages/project/algorithms/algorithms'
import { CaptureSets } from 'pages/project/capture-sets/capture-sets'
import { DefaultFilters } from 'pages/project/default-filters/default-filters'
import { Devices } from 'pages/project/entities/devices'
import { Sites } from 'pages/project/entities/sites'
import { Exports } from 'pages/project/exports/exports'
import { General } from 'pages/project/general/general'
import { Pipelines } from 'pages/project/pipelines/pipelines'
import { ProcessingServices } from 'pages/project/processing-services/processing-services'
import { Processing } from 'pages/project/processing/processing'
import Project from 'pages/project/project'
import { Storage } from 'pages/project/storage/storage'
import { Summary } from 'pages/project/summary/summary'
import { Team } from 'pages/project/team/team'
import { Projects } from 'pages/projects/projects'
import SessionDetails from 'pages/session-details/session-details'
import { Sessions } from 'pages/sessions/sessions'
import { Species } from 'pages/species/species'
import { TaxaListDetails } from 'pages/taxa-list-details/taxa-list-details'
import { TaxaLists } from 'pages/taxa-lists/taxa-lists'
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
      <div id={INTRO_CONTAINER_ID} className="no-print">
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
          <Route path="" element={<Project />}>
            <Route
              path=""
              element={<Navigate to={{ pathname: 'summary' }} replace={true} />}
            />
            <Route path="summary" element={<Summary />} />
            <Route path="capture-sets" element={<CaptureSets />} />
            <Route path="collections" element={<Collections />} />
            <Route path="taxa-lists" element={<TaxaLists />} />
            <Route path="taxa-lists/:id?" element={<TaxaListDetails />} />
            <Route
              path="taxa-lists/:id?/taxa/:taxonId"
              element={<TaxaListDetails />}
            />
            <Route path="exports/:id?" element={<Exports />} />
            <Route
              path="processing-services/:id?"
              element={<ProcessingServices />}
            />
            <Route path="pipelines/:id?" element={<Pipelines />} />
            <Route path="algorithms/:id?" element={<Algorithms />} />
            <Route path="sites" element={<Sites />} />
            <Route path="devices" element={<Devices />} />
            <Route path="general" element={<General />} />
            <Route path="team" element={<Team />} />
            <Route path="default-filters" element={<DefaultFilters />} />
            <Route path="storage" element={<Storage />} />
            <Route path="processing" element={<Processing />} />
          </Route>
          <Route path="jobs/:id?" element={<Jobs />} />
          <Route path="deployments/:id?" element={<Deployments />} />
          <Route path="captures" element={<Captures />} />
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
    if (projectDetails.error) {
      setProjectBreadcrumb(undefined)
    } else {
      setProjectBreadcrumb({
        title: projectDetails.project?.name ?? '',
        path: APP_ROUTES.PROJECT_DETAILS({ projectId: projectId as string }),
      })
    }

    return () => {
      setProjectBreadcrumb(undefined)
    }
  }, [projectDetails.project, projectDetails.error])

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

/* We have changed the wording from "Collections" to "Capture sets". This will redirect users to the new route. */
const Collections = () => {
  const { projectId } = useParams()

  return (
    <Navigate
      replace
      to={APP_ROUTES.CAPTURE_SETS({ projectId: projectId as string })}
    />
  )
}
