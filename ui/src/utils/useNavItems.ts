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

  const navItems: NavigationItem[] = useMemo(
    () => [
      {
        id: 'overview',
        title: translate(STRING.NAV_ITEM_OVERVIEW),
        icon: IconType.Overview,
        path: '/overview',
      },
      {
        id: 'batch-id',
        title: translate(STRING.NAV_ITEM_BATCH_ID),
        icon: IconType.BatchId,
        path: '/batch-id',
      },
      {
        id: 'deployments',
        title: translate(STRING.NAV_ITEM_DEPLOYMENTS),
        icon: IconType.Deployments,
        count: 0,
        path: '/deployments',
        matchPath: '/deployments/*',
      },
      {
        id: 'sessions',
        title: translate(STRING.NAV_ITEM_SESSIONS),
        icon: IconType.Sessions,
        count: 0,
        path: '/sessions',
        matchPath: '/sessions/*',
      },
      {
        id: 'occurrences',
        title: translate(STRING.NAV_ITEM_OCCURRENCES),
        icon: IconType.Occurrences,
        count: 0,
        path: '/occurrences',
        matchPath: '/occurrences/*',
      },
      {
        id: 'species',
        title: translate(STRING.NAV_ITEM_SPECIES),
        icon: IconType.Species,
        count: 0,
        path: '/species',
        matchPath: '/species/*',
      },
    ],
    []
  )

  const activeNavItem =
    navItems.find(
      (navItem) =>
        !!matchPath(navItem.matchPath ?? navItem.path, location.pathname)
    ) ?? navItems[0]

  return { navItems, activeNavItemId: activeNavItem.id }
}
