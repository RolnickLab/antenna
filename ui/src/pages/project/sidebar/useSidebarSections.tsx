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

const getSidebarSections = ({
  projectId,
  canUpdate,
}: {
  projectId: string
  canUpdate?: boolean
}): { title?: string; items: SidebarItem[] }[] => [
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
        matchPath: APP_ROUTES.PROCESSING_SERVICE_DETAILS({
          projectId: ':projectId',
          processingServiceId: '*',
        }),
      },
      {
        id: 'pipelines',
        title: translate(STRING.NAV_ITEM_PIPELINES),
        path: APP_ROUTES.PIPELINES({ projectId }),
        matchPath: APP_ROUTES.PIPELINE_DETAILS({
          projectId: ':projectId',
          pipelineId: '*',
        }),
      },
      {
        id: 'algorithms',
        title: translate(STRING.NAV_ITEM_ALGORITHMS),
        path: APP_ROUTES.ALGORITHMS({ projectId }),
        matchPath: APP_ROUTES.ALGORITHM_DETAILS({
          projectId: ':projectId',
          algorithmId: '*',
        }),
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
      ...(canUpdate
        ? [
            {
              id: 'general',
              title: translate(STRING.NAV_ITEM_GENERAL),
              path: APP_ROUTES.GENERAL({ projectId }),
            },
          ]
        : []),
      {
        id: 'storage',
        title: translate(STRING.NAV_ITEM_STORAGE),
        path: APP_ROUTES.STORAGE({ projectId }),
      },
    ],
  },
]

export const useSidebarSections = ({
  projectId,
  canUpdate,
}: {
  projectId: string
  canUpdate?: boolean
}) => {
  const location = useLocation()
  const sidebarSections = useMemo(
    () => getSidebarSections({ projectId, canUpdate }),
    [projectId, canUpdate]
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
