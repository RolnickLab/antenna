import { API_ROUTES } from 'data-services/constants'
import { Project } from 'data-services/models/project'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Error } from 'pages/error/error'
import { useOutletContext } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { Collections } from './collections/collections'
import { DeploymentsMap } from './deployments-map/deployments-map'
import { Entities } from './entities/entities'
import styles from './overview.module.scss'
import { Pipelines } from './pipelines/pipelines'
import { Summary } from './summary/summary'

export const Overview = () => {
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
          <Tabs.Trigger
            value="pipelines"
            label={translate(STRING.TAB_ITEM_PIPELINES)}
          />
          <Tabs.Trigger
            value="storage"
            label={translate(STRING.TAB_ITEM_STORAGE)}
          />
          <Tabs.Trigger
            value="sites"
            label={translate(STRING.TAB_ITEM_SITES)}
          />
          <Tabs.Trigger
            value="devices"
            label={translate(STRING.TAB_ITEM_DEVICES)}
          />
        </Tabs.List>
        <Tabs.Content value="summary">
          <Summary project={project} />
        </Tabs.Content>
        <Tabs.Content value="collections">
          <Collections />
        </Tabs.Content>
        <Tabs.Content value="pipelines">
          <Pipelines />
        </Tabs.Content>
        <Tabs.Content value="storage">
          <Entities collection={API_ROUTES.STORAGE} />
        </Tabs.Content>
        <Tabs.Content value="sites">
          <Entities collection={API_ROUTES.SITES} />
        </Tabs.Content>
        <Tabs.Content value="devices">
          <Entities collection={API_ROUTES.DEVICES} />
        </Tabs.Content>
      </Tabs.Root>
    </>
  )
}

export default Overview
