import { useProjects } from 'data-services/hooks/projects/useProjects'
import { PageFooter } from 'design-system/components/page-footer/page-footer'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { PaginationBar } from 'design-system/components/pagination-bar/pagination-bar'
import { Error } from 'pages/error/error'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { STRING, translate } from 'utils/language'
import { usePagination } from 'utils/usePagination'
import { UserPermission } from 'utils/user/types'
import { ProjectGallery } from './project-gallery'
import styles from './projects.module.scss'

export const Projects = () => {
  const { pagination, setPage } = usePagination()
  const { projects, total, userPermissions, isLoading, isFetching, error } =
    useProjects({ pagination })
  const canCreate = userPermissions?.includes(UserPermission.Create)

  if (!isLoading && error) {
    return <Error error={error} />
  }

  return (
    <>
      <PageHeader
        title={translate(STRING.NAV_ITEM_PROJECTS)}
        subTitle={translate(STRING.RESULTS, { total: projects?.length ?? 0 })}
        isLoading={isLoading}
        isFetching={isFetching}
      >
        {canCreate && <NewProjectDialog />}
      </PageHeader>
      <div className={styles.galleryContent}>
        <ProjectGallery projects={projects} isLoading={isLoading} />
      </div>
      <PageFooter>
        {projects?.length ? (
          <PaginationBar
            pagination={pagination}
            total={total}
            setPage={setPage}
          />
        ) : null}
      </PageFooter>
    </>
  )
}
