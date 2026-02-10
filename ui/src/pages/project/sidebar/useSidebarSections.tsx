import { ProjectDetails } from 'data-services/models/project-details'
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
  project: ProjectDetails
): { title?: string; items: SidebarItem[] }[] => [
  {
    items: [
      {
        id: 'summary',
        title: translate(STRING.NAV_ITEM_SUMMARY),
        path: APP_ROUTES.SUMMARY({ projectId: project.id }),
      },
      {
        id: 'capture-sets',
        title: translate(STRING.NAV_ITEM_CAPTURE_SETS),
        path: APP_ROUTES.CAPTURE_SETS({ projectId: project.id }),
      },
      {
        id: 'exports',
        title: translate(STRING.NAV_ITEM_EXPORTS),
        path: APP_ROUTES.EXPORTS({ projectId: project.id }),
      },
    ],
  },
  {
    title: 'Processing',
    items: [
      {
        id: 'processing-services',
        title: translate(STRING.NAV_ITEM_PROCESSING_SERVICES),
        path: APP_ROUTES.PROCESSING_SERVICES({ projectId: project.id }),
        matchPath: APP_ROUTES.PROCESSING_SERVICE_DETAILS({
          projectId: ':projectId',
          processingServiceId: '*',
        }),
      },
      {
        id: 'pipelines',
        title: translate(STRING.NAV_ITEM_PIPELINES),
        path: APP_ROUTES.PIPELINES({ projectId: project.id }),
        matchPath: APP_ROUTES.PIPELINE_DETAILS({
          projectId: ':projectId',
          pipelineId: '*',
        }),
      },
      {
        id: 'algorithms',
        title: translate(STRING.NAV_ITEM_ALGORITHMS),
        path: APP_ROUTES.ALGORITHMS({ projectId: project.id }),
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
        path: APP_ROUTES.SITES({ projectId: project.id }),
      },
      {
        id: 'devices',
        title: translate(STRING.NAV_ITEM_DEVICES),
        path: APP_ROUTES.DEVICES({ projectId: project.id }),
      },
    ],
  },
  {
    title: 'Settings',
    items: [
      ...(project.canUpdate
        ? [
            {
              id: 'general',
              title: translate(STRING.NAV_ITEM_GENERAL),
              path: APP_ROUTES.GENERAL({ projectId: project.id }),
            },
            {
              id: 'default-filters',
              title: translate(STRING.NAV_ITEM_DEFAULT_FILTERS),
              path: APP_ROUTES.DEFAULT_FILTERS({ projectId: project.id }),
            },
          ]
        : []),
      ...(project.isMember
        ? [
            {
              id: 'team',
              title: translate(STRING.NAV_ITEM_TEAM),
              path: APP_ROUTES.TEAM({ projectId: project.id }),
            },
          ]
        : []),
      {
        id: 'storage',
        title: translate(STRING.NAV_ITEM_STORAGE),
        path: APP_ROUTES.STORAGE({ projectId: project.id }),
      },
      ...(project.canUpdate
        ? [
            {
              id: 'processing',
              title: translate(STRING.NAV_ITEM_PROCESSING),
              path: APP_ROUTES.PROCESSING({ projectId: project.id }),
            },
          ]
        : []),
    ],
  },
]

export const useSidebarSections = (project: ProjectDetails) => {
  const location = useLocation()
  const sidebarSections = useMemo(() => getSidebarSections(project), [project])
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
