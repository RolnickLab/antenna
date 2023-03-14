import { matchPath, useLocation } from 'react-router-dom'

interface NavigatinonItem {
  id: string
  title: string
  count?: number
  path: string
}

const NAV_ITEMS: NavigatinonItem[] = [
  { id: 'overview', title: 'Overview', path: '/overview' },
  { id: 'deployments', title: 'Deployments', count: 0, path: '/deployments' },
  { id: 'sessions', title: 'Sessions', count: 0, path: '/sessions' },
  { id: 'occurrences', title: 'Occurrences', count: 0, path: '/occurrences' },
  { id: 'species', title: 'Species', count: 0, path: '/species' },
  { id: 'members', title: 'Members', count: 0, path: '/members' },
  { id: 'identifiers', title: 'Identifiers', count: 0, path: '/identifiers' },
]

export const useNavItems = () => {
  const location = useLocation()

  const activeNavItem =
    NAV_ITEMS.find((navItem) => !!matchPath(navItem.path, location.pathname)) ??
    NAV_ITEMS[0]

  return { navItems: NAV_ITEMS, activeNavItemId: activeNavItem.id }
}
