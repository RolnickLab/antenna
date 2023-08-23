import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { Table } from 'design-system/components/table/table/table'
import { DeploymentDetailsDialog } from 'pages/deployment-details/deployment-details-dialog'
import { NewDeploymentDialog } from 'pages/deployment-details/new-deployment-dialog'
import { Error } from 'pages/error/error'
import { useParams } from 'react-router-dom'
import { useClientSideSort } from 'utils/useClientSideSort'
import { columns } from './deployment-columns'
import styles from './deployments.module.scss'

export const Deployments = () => {
  const { projectId, id } = useParams()
  const { deployments, isLoading, isFetching, error } = useDeployments()
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'desc' },
  })

  if (!isLoading && error) {
    return <Error />
  }

  return (
    <>
      {isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo isLoading={isLoading} />
        </div>
      )}
      <Table
        items={sortedItems}
        isLoading={isLoading}
        columns={columns(projectId as string)}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {!isLoading && id ? (
        <DeploymentDetailsDialog id={id} />
      ) : (
        <NewDeploymentDialog />
      )}
    </>
  )
}
