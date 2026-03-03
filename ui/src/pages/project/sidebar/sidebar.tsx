import classNames from 'classnames'
import { ProjectDetails } from 'data-services/models/project-details'
import { Badge } from 'design-system/components/badge/badge'
import { ChevronRightIcon, PenIcon } from 'lucide-react'
import { buttonVariants, Tooltip } from 'nova-ui-kit'
import { Fragment, ReactNode, useContext, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useSidebarSections } from './useSidebarSections'

export const Sidebar = ({ project }: { project: ProjectDetails }) => {
  const { sidebarSections, activeItem } = useSidebarSections(project)
  const { setMainBreadcrumb } = useContext(BreadcrumbContext)

  useEffect(() => {
    if (activeItem) {
      setMainBreadcrumb({ title: activeItem.title, path: activeItem.path })
    }
    return () => {
      setMainBreadcrumb(undefined)
    }
  }, [activeItem])

  return (
    <div className="w-full h-min shrink-0 p-0 rounded-md border border-border overflow-hidden bg-background md:w-72">
      {project.image ? (
        <img src={project.image} alt="" />
      ) : (
        <div className="aspect-video flex items-center justify-center">
          <Link
            to={getAppRoute({
              to: APP_ROUTES.GENERAL({ projectId: project.id }),
            })}
            className={classNames(
              buttonVariants({ size: 'small', variant: 'ghost' })
            )}
          >
            <PenIcon className="w-4 h-4" />
            <span>Set cover image</span>
          </Link>
        </div>
      )}
      <div className="grid gap-1 py-3">
        <div className="grid px-4 py-1 gap-2">
          <div className="flex items-start justify-between gap-2">
            <span className="body-large">{project.name}</span>
            {project.isDraft ? <DraftBadge project={project} /> : null}
          </div>
          {project.description?.length ? (
            <span className="body-small text-muted-foreground">
              {project.description}
            </span>
          ) : null}
        </div>
        <Separator />
        {sidebarSections.map((section, index) => (
          <Fragment key={index}>
            <SidebarSection title={section.title}>
              {section.items.map((item) => (
                <SidebarItem
                  key={item.id}
                  active={activeItem?.id === item.id}
                  to={item.path}
                >
                  {item.title}
                </SidebarItem>
              ))}
            </SidebarSection>
            {index < sidebarSections.length - 1 ? <Separator /> : null}
          </Fragment>
        ))}
      </div>
    </div>
  )
}

const Separator = () => <div className="w-full h-[1px] my-2 bg-border" />

const SidebarSection = ({
  children,
  title,
}: {
  children: ReactNode
  title?: string
}) => (
  <div className="grid px-4 gap-1">
    {title ? (
      <span className="py-1 body-base font-medium text-muted-foreground/50">
        {title}
      </span>
    ) : null}
    {children}
  </div>
)

const SidebarItem = ({
  active,
  children,
  to,
}: {
  active?: boolean
  children: string
  to: string
}) => (
  <Link
    className={classNames('body-base py-1', {
      'font-bold text-primary': active,
    })}
    to={to}
  >
    {children}
  </Link>
)

export const DraftBadge = ({ project }: { project: ProjectDetails }) => (
  <Tooltip.Provider delayDuration={0}>
    <Tooltip.Root>
      <Tooltip.Trigger>
        <Badge label={translate(STRING.DRAFT)} />
      </Tooltip.Trigger>
      <Tooltip.Content side="bottom" className="p-4 space-y-4 max-w-xs">
        <p className="whitespace-normal">{translate(STRING.MESSAGE_DRAFTS)}</p>
        {project.canUpdate ? (
          <Link
            className={classNames(
              buttonVariants({ size: 'small', variant: 'outline' }),
              '!w-auto'
            )}
            to={APP_ROUTES.GENERAL({ projectId: project.id })}
          >
            <span>Configure</span>
            <ChevronRightIcon className="w-4 h-4" />
          </Link>
        ) : null}
      </Tooltip.Content>
    </Tooltip.Root>
  </Tooltip.Provider>
)
