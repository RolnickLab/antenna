import classNames from 'classnames'
import { Project } from 'data-services/models/project'
import { DeleteProjectDialog } from 'pages/project-details/delete-project-dialog'
import { EditProjectDialog } from 'pages/project-details/edit-project-dialog'
import { Fragment, ReactNode, useContext, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { BreadcrumbContext } from 'utils/breadcrumbContext'
import { useSidebarSections } from './useSidebarSections'

export const Sidebar = ({ project }: { project: Project }) => {
  const { projectId } = useParams()
  const { sidebarSections, activeItem } = useSidebarSections(
    projectId as string
  )
  const { setDetailBreadcrumb } = useContext(BreadcrumbContext)

  useEffect(() => {
    if (activeItem) {
      setDetailBreadcrumb({ title: activeItem.title, path: activeItem.path })
    }
    return () => {
      setDetailBreadcrumb(undefined)
    }
  }, [activeItem])

  return (
    <div className="w-full h-min shrink-0 p-0 rounded-md border border-border overflow-hidden bg-background md:w-72">
      {project.image ? <img src={project.image} alt="" /> : null}
      <div className="grid gap-1 py-3">
        <div className="grid px-4 py-1 gap-2">
          <span className="body-large">{project.name}</span>
          {project.description?.length ? (
            <span className="body-small text-muted-foreground">
              {project.description}
            </span>
          ) : null}
          <div className="flex gap-2 items-center justify-end">
            <EditProjectDialog id={projectId as string} />
            <DeleteProjectDialog id={projectId as string} />
          </div>
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
