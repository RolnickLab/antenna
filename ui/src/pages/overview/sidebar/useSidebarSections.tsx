import { useMemo } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

interface SidebarItem {
  id: string
  matchPath?: string
  path: string
  title: string
}

const getSidebarSections = (
  projectId: string
): { title?: string; items: SidebarItem[] }[] => [
  {
    items: [
      {
        id: 'summary',
        title: translate(STRING.NAV_ITEM_SUMMARY),
        path: APP_ROUTES.SUMMARY({ projectId }),
      },
      {
        id: 'collections',
        title: translate(STRING.NAV_ITEM_COLLECTIONS),
        path: APP_ROUTES.COLLECTIONS({ projectId }),
        matchPath: APP_ROUTES.COLLECTION_DETAILS({
          projectId: ':projectId',
          collectionId: '*',
        }),
      },
    ],
  },
  {
    title: 'Processing',
    items: [
      {
        id: 'processing-services',
        title: translate(STRING.NAV_ITEM_PROCESSING_SERVICES),
        path: APP_ROUTES.PROCESSING_SERVICES({ projectId }),
      },
      {
        id: 'pipelines',
        title: translate(STRING.NAV_ITEM_PIPELINES),
        path: APP_ROUTES.PIPELINES({ projectId }),
      },
    ],
  },
  {
    title: 'Metadata',
    items: [
      {
        id: 'sites',
        title: translate(STRING.NAV_ITEM_SITES),
        path: APP_ROUTES.SITES({ projectId }),
      },
      {
        id: 'devices',
        title: translate(STRING.NAV_ITEM_DEVICES),
        path: APP_ROUTES.DEVICES({ projectId }),
      },
    ],
  },
  {
    title: 'Settings',
    items: [
      {
        id: 'storage',
        title: translate(STRING.NAV_ITEM_STORAGE),
        path: APP_ROUTES.STORAGE({ projectId }),
      },
    ],
  },
]

export const useSidebarSections = (projectId: string) => {
  const location = useLocation()
  const sidebarSections = useMemo(
    () => getSidebarSections(projectId as string),
    [projectId]
  )
  const activeItem = useMemo(() => {
    const items = sidebarSections.map((section) => section.items).flat()

    return items.find(
      (item) => !!matchPath(item.matchPath ?? item.path, location.pathname)
    )
  }, [location.pathname, sidebarSections])

  sidebarSections
    .map(({ items }) => items)
    .flat()
    .find((item) => !!matchPath(item.path, location.pathname))

  return { sidebarSections, activeItem }
}
