import { useStatus } from 'data-services/hooks/useStatus'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import { matchPath, useLocation, useParams } from 'react-router-dom'
import { getRoute } from './getRoute'
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
        path: getRoute({
          projectId: projectId as string,
          collection: undefined,
        }),
        matchPath: '/projects/:projectId',
      },
      {
        id: 'jobs',
        title: translate(STRING.NAV_ITEM_JOBS),
        icon: IconType.BatchId,
        path: getRoute({ projectId: projectId as string, collection: 'jobs' }),
        matchPath: '/projects/:projectId/jobs/*',
      },
      {
        id: 'deployments',
        title: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        icon: IconType.Deployments,
        count: status?.numDeployments,
        path: getRoute({
          projectId: projectId as string,
          collection: 'deployments',
        }),
        matchPath: '/projects/:projectId/deployments/*',
      },
      {
        id: 'sessions',
        title: translate(STRING.NAV_ITEM_SESSIONS),
        icon: IconType.Sessions,
        count: status?.numSessions,
        path: getRoute({
          projectId: projectId as string,
          collection: 'sessions',
        }),
        matchPath: '/projects/:projectId/sessions/*',
      },
      {
        id: 'occurrences',
        title: translate(STRING.NAV_ITEM_OCCURRENCES),
        icon: IconType.Occurrences,
        count: status?.numOccurrences,
        path: getRoute({
          projectId: projectId as string,
          collection: 'occurrences',
        }),
        matchPath: '/projects/:projectId/occurrences/*',
      },
      {
        id: 'species',
        title: translate(STRING.NAV_ITEM_SPECIES),
        icon: IconType.Species,
        count: status?.numSpecies,
        path: getRoute({
          projectId: projectId as string,
          collection: 'species',
        }),
        matchPath: '/projects/:projectId/species/*',
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
