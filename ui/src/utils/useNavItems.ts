import { useDeployments } from 'data-services/useDeployments'
import { useOccurrences } from 'data-services/useOccurrences'
import { IconType } from 'design-system/components/icon/icon'
import { useMemo } from 'react'
import { matchPath, useLocation } from 'react-router-dom'

interface NavigatinonItem {
  id: string
  title: string
  icon: IconType
  count?: number
  path: string
}

export const useNavItems = () => {
  const location = useLocation()
  const deployments = useDeployments()
  const occurrences = useOccurrences()

  const navItems: NavigatinonItem[] = useMemo(
    () => [
      {
        id: 'overview',
        title: 'Overview',
        icon: IconType.Overview,
        path: '/overview',
      },
      {
        id: 'deployments',
        title: 'Deployments',
        icon: IconType.Deployments,
        count: deployments.length,
        path: '/deployments',
      },
      {
        id: 'sessions',
        title: 'Sessions',
        icon: IconType.Sessions,
        count: 0,
        path: '/sessions',
      },
      {
        id: 'occurrences',
        title: 'Occurrences',
        icon: IconType.Occurrences,
        count: occurrences.length,
        path: '/occurrences',
      },
      {
        id: 'species',
        title: 'Species',
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
