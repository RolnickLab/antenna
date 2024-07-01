import { useProjects } from 'data-services/hooks/projects/useProjects'
import { PageHeader } from 'design-system/components/page-header/page-header'
import { Error } from 'pages/error/error'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { ProjectGallery } from './project-gallery'
import styles from './projects.module.scss'

export const Projects = () => {
  const { projects, userPermissions, isLoading, isFetching, error } =
    useProjects()
  const canCreate = userPermissions?.includes(UserPermission.Create)

  if (!isLoading && error) {
    return <Error />
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
    </>
  )
}
