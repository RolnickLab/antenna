import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useProjects } from 'data-services/hooks/projects/useProjects'
import { Error } from 'pages/error/error'
import { NewProjectDialog } from 'pages/project-details/new-project-dialog'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { ProjectGallery } from './project-gallery'
import styles from './projects.module.scss'

export const Projects = () => {
  const { projects, userPermissions, isLoading, isFetching, error } =
    useProjects()

  if (!isLoading && error) {
    return <Error />
  }

  const canCreate = userPermissions?.includes(UserPermission.Create)

  return (
    <>
      <div className={styles.infoWrapper}>
        {isFetching && <FetchInfo isLoading={isLoading} />}
      </div>
      <div className={styles.header}>
        <h1 className={styles.title}>{translate(STRING.NAV_ITEM_PROJECTS)}</h1>
      </div>
      <div className={styles.divider} />
      <ProjectGallery projects={projects} isLoading={isLoading} />
      <div className={styles.spacer} />
      {canCreate && <NewProjectDialog />}
    </>
  )
}
