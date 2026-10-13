import { useStatus } from 'data-services/hooks/useStatus'
import { useMemo } from 'react'
import { matchPath, useLocation, useParams } from 'react-router-dom'
import { APP_ROUTES } from './constants'
import { STRING, translate } from './language'
import { useUser } from './user/userContext'

interface NavigationItem {
  id: string
  title: string
  count?: number
  path?: string
  matchPath: string
}

export const useNavItems = () => {
  const location = useLocation()
  const { projectId } = useParams()
  const { status } = useStatus(projectId)
  const {
    user: { loggedIn },
  } = useUser()

  const navItems: NavigationItem[] = useMemo(
    () => [
      {
        id: 'project',
        title: translate(STRING.NAV_ITEM_PROJECT),
        path: APP_ROUTES.PROJECT_DETAILS({ projectId: projectId as string }),
        matchPath: APP_ROUTES.PROJECT_DETAILS({ projectId: ':projectId' }),
      },
      ...(loggedIn
        ? [
            {
              id: 'jobs',
              title: translate(STRING.NAV_ITEM_JOBS),
              path: APP_ROUTES.JOBS({ projectId: projectId as string }),
              matchPath: APP_ROUTES.JOB_DETAILS({
                projectId: ':projectId',
                jobId: '*',
              }),
            },
          ]
        : []),
      {
        id: 'captures',
        title: translate(STRING.NAV_ITEM_CAPTURES),
        count: status?.numCaptures,
        path: APP_ROUTES.CAPTURES({ projectId: projectId as string }),
        matchPath: APP_ROUTES.CAPTURES({ projectId: ':projectId' }),
      },
      {
        id: 'deployments',
        title: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        count: status?.numDeployments,
        path: APP_ROUTES.DEPLOYMENTS({ projectId: projectId as string }),
        matchPath: APP_ROUTES.DEPLOYMENT_DETAILS({
          projectId: ':projectId',
          deploymentId: '*',
        }),
      },
      {
        id: 'sessions',
        title: translate(STRING.NAV_ITEM_SESSIONS),
        count: status?.numSessions,
        path: APP_ROUTES.SESSIONS({ projectId: projectId as string }),
        matchPath: APP_ROUTES.SESSION_DETAILS({
          projectId: ':projectId',
          sessionId: '*',
        }),
      },
      {
        id: 'occurrences',
        title: translate(STRING.NAV_ITEM_OCCURRENCES),
        count: status?.numOccurrences,
        path: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        matchPath: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId: ':projectId',
          occurrenceId: '*',
        }),
      },
      {
        id: 'taxa',
        title: translate(STRING.NAV_ITEM_TAXA),
        count: status?.numSpecies,
        path: APP_ROUTES.TAXA({ projectId: projectId as string }),
        matchPath: APP_ROUTES.TAXON_DETAILS({
          projectId: ':projectId',
          taxonId: '*',
        }),
      },
    ],
    [status, projectId, loggedIn]
  )

  const activeNavItem =
    navItems.find(
      (navItem) => !!matchPath(navItem.matchPath, location.pathname)
    ) ?? navItems[0]

  return { navItems, activeNavItem }
}
