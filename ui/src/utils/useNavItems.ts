import { useDeployments } from 'data-services/useDeployments'
import { useOccurrences } from 'data-services/useOccurrences'
import { useSessions } from 'data-services/useSessions'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { STRING, translate } from './language'

interface NavigatinonItem {
  id: string
  title: string
  icon?: IconType
  count?: number
  path: string
}

export const useNavItems = () => {
  const location = useLocation()
  const deployments = useDeployments()
  const sessions = useSessions()
  const occurrences = useOccurrences()

  const navItems: NavigatinonItem[] = useMemo(
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
        count: deployments.length,
        path: '/deployments',
      },
      {
        id: 'sessions',
        title: translate(STRING.NAV_ITEM_SESSIONS),
        icon: IconType.Sessions,
        count: sessions.length,
        path: '/sessions',
      },
      {
        id: 'occurrences',
        title: translate(STRING.NAV_ITEM_OCCURRENCES),
        icon: IconType.Occurrences,
        count: occurrences.length,
        path: '/occurrences',
      },
      {
        id: 'species',
        title: translate(STRING.NAV_ITEM_SPECIES),
        icon: IconType.Species,
        count: 0,
        path: '/species',
      },
    ],
    [deployments, occurrences]
  )

  const activeNavItem =
    navItems.find((navItem) => !!matchPath(navItem.path, location.pathname)) ??
    navItems[0]

  return { navItems, activeNavItemId: activeNavItem.id }
}
