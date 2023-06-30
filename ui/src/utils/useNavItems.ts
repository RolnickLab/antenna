import { useStatus } from 'data-services/hooks/useStatus'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { STRING, translate } from './language'

interface NavigationItem {
  id: string
  title: string
  icon?: IconType
  count?: number
  path: string
  matchPath?: string
}

export const useNavItems = () => {
  const location = useLocation()
  const { status } = useStatus()

  const navItems: NavigationItem[] = useMemo(
    () => [
      {
        id: 'overview',
        title: translate(STRING.NAV_ITEM_OVERVIEW),
        icon: IconType.Overview,
        path: '/overview',
      },
      {
        id: 'jobs',
        title: translate(STRING.NAV_ITEM_JOBS),
        icon: IconType.BatchId,
        path: '/jobs',
        matchPath: '/jobs/*',
      },
      {
        id: 'deployments',
        title: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        icon: IconType.Deployments,
        count: status?.numDeployments,
        path: '/deployments',
        matchPath: '/deployments/*',
      },
      {
        id: 'sessions',
        title: translate(STRING.NAV_ITEM_SESSIONS),
        icon: IconType.Sessions,
        count: status?.numSessions,
        path: '/sessions',
        matchPath: '/sessions/*',
      },
      {
        id: 'occurrences',
        title: translate(STRING.NAV_ITEM_OCCURRENCES),
        icon: IconType.Occurrences,
        count: status?.numOccurrences,
        path: '/occurrences',
        matchPath: '/occurrences/*',
      },
      {
        id: 'species',
        title: translate(STRING.NAV_ITEM_SPECIES),
        icon: IconType.Species,
        count: status?.numSpecies,
        path: '/species',
        matchPath: '/species/*',
      },
    ],
    [status]
  )

  const activeNavItem =
    navItems.find(
      (navItem) =>
        !!matchPath(navItem.matchPath ?? navItem.path, location.pathname)
    ) ?? navItems[0]

  return { navItems, activeNavItemId: activeNavItem.id }
}
