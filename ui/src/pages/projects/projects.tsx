import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useProjects } from 'data-services/hooks/projects/useProjects'
import { Error } from 'pages/error/error'
import { STRING, translate } from 'utils/language'
import { ProjectGallery } from './project-gallery'
import styles from './projects.module.scss'

export const Projects = () => {
  const { projects, isLoading, isFetching, error } = useProjects()

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      <div className={styles.infoWrapper}>
        {isFetching && <FetchInfo isLoading={isLoading} />}
      </div>
      <h1 className={styles.title}>{translate(STRING.NAV_ITEM_PROJECTS)}</h1>
      <div className={styles.divider} />
      <ProjectGallery projects={projects} isLoading={isLoading} />
    </>
  )
}
