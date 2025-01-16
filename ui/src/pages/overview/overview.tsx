import { ErrorState } from 'components/error-state/error-state'
import { API_ROUTES } from 'data-services/constants'
import { Project } from 'data-services/models/project'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import * as Tabs from 'design-system/components/tabs/tabs'
import { Helmet } from 'react-helmet-async'
import { useOutletContext } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useSelectedView } from 'utils/useSelectedView'
import { Collections } from './collections/collections'
import { DeploymentsMap } from './deployments-map/deployments-map'
import { Entities } from './entities/entities'
import styles from './overview.module.scss'
import { Pipelines } from './pipelines/pipelines'
import { StorageSources } from './storage/storage'
import { Summary } from './summary/summary'

export const Overview = () => {
  const { selectedView, setSelectedView } = useSelectedView('summary', 'tab')
  const { project, isLoading, error } = useOutletContext<{
    project?: Project
    isLoading: boolean
    isFetching: boolean
    error?: unknown
  }>()

  if (!isLoading && error) {
    return <ErrorState error={error} />
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
      <Helmet>
        <meta property="og:image" content={project?.image} />
      </Helmet>
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
      <Tabs.Root value={selectedView} onValueChange={setSelectedView}>
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
          <StorageSources />
        </Tabs.Content>
        <Tabs.Content value="sites">
          <Entities
            title={translate(STRING.TAB_ITEM_SITES)}
            collection={API_ROUTES.SITES}
            type="site"
            tooltip={translate(STRING.TOOLTIP_SITE)}
          />
        </Tabs.Content>
        <Tabs.Content value="devices">
          <Entities
            title={translate(STRING.TAB_ITEM_DEVICES)}
            collection={API_ROUTES.DEVICES}
            type="device"
            tooltip={translate(STRING.TOOLTIP_DEVICE_TYPE)}
          />
        </Tabs.Content>
      </Tabs.Root>
    </>
  )
}

export default Overview
