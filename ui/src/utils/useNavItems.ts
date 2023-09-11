import { useStatus } from 'data-services/hooks/useStatus'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import { matchPath, useLocation, useParams } from 'react-router-dom'
import { APP_ROUTES } from './constants'
import { STRING, translate } from './language'

interface NavigationItem {
  id: string
  title: string
  icon?: IconType
  count?: number
  path: string
  matchPath: string
}

export const useNavItems = () => {
  const location = useLocation()
  const { projectId } = useParams()
  const { status } = useStatus(projectId)

  const navItems: NavigationItem[] = useMemo(
    () => [
      {
        id: 'overview',
        title: translate(STRING.NAV_ITEM_OVERVIEW),
        icon: IconType.Overview,
        path: APP_ROUTES.PROJECT_DETAILS({ projectId: projectId as string }),
        matchPath: APP_ROUTES.PROJECT_DETAILS({ projectId: ':projectId' }),
      },
      {
        id: 'jobs',
        title: translate(STRING.NAV_ITEM_JOBS),
        icon: IconType.BatchId,
        path: APP_ROUTES.JOBS({ projectId: projectId as string }),
        matchPath: APP_ROUTES.JOB_DETAILS({
          projectId: ':projectId',
          jobId: '*',
        }),
      },
      {
        id: 'deployments',
        title: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        icon: IconType.Deployments,
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
        icon: IconType.Sessions,
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
        icon: IconType.Occurrences,
        count: status?.numOccurrences,
        path: APP_ROUTES.OCCURRENCES({ projectId: projectId as string }),
        matchPath: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId: ':projectId',
          occurrenceId: '*',
        }),
      },
      {
        id: 'species',
        title: translate(STRING.NAV_ITEM_SPECIES),
        icon: IconType.Species,
        count: status?.numSpecies,
        path: APP_ROUTES.SPECIES({ projectId: projectId as string }),
        matchPath: APP_ROUTES.SPECIES_DETAILS({
          projectId: ':projectId',
          speciesId: '*',
        }),
      },
    ],
    [status, projectId]
  )

  const activeNavItem =
    navItems.find(
      (navItem) => !!matchPath(navItem.matchPath, location.pathname)
    ) ?? navItems[0]

  return { navItems, activeNavItemId: activeNavItem.id }
}
