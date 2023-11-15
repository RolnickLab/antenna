import { Project } from 'data-services/models/project'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { useOutletContext } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { Collections } from './collections/collections'
import { DeploymentsMap } from './deployments-map/deployments-map'
import styles from './overview.module.scss'
import { Summary } from './summary/summary'

const Overview = () => {
  const { project, isLoading, error } = useOutletContext<{
    project?: Project
    isLoading: boolean
    isFetching: boolean
    error?: unknown
  }>()

  if (!isLoading && error) {
    return <Error />
  }

  if (isLoading || !project) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <>
      <div className={styles.about}>
        <div className={styles.aboutImage}>
          {project.image ? (
            <img src={project.image} alt="" />
          ) : (
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Neutral}
              size={32}
            />
          )}
        </div>
        <div className={styles.aboutInfo}>
          <h1 className={styles.title}>{project.name}</h1>
          <p className={styles.description}>{project.description}</p>
          <DeploymentsMap deployments={project.deployments} />
        </div>
      </div>
      <Tabs.Root defaultValue="summary">
        <Tabs.List>
          <Tabs.Trigger
            value="summary"
            label={translate(STRING.TAB_ITEM_SUMMARY)}
          />
          <Tabs.Trigger
            value="collections"
            label={translate(STRING.TAB_ITEM_COLLECTIONS)}
          />
        </Tabs.List>
        <Tabs.Content value="summary">
          <Summary project={project} />
        </Tabs.Content>
        <Tabs.Content value="collections">
          <Collections />
        </Tabs.Content>
      </Tabs.Root>
    </>
  )
}

export default Overview
