import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useDeployments } from 'data-services/hooks/useDeployments'
import { Table } from 'design-system/components/table/table/table'
import { DeploymentDetailsDialog } from 'pages/deployment-details/deployment-details-dialog'
import { NewDeploymentDialog } from 'pages/deployment-details/new-deployment-dialog'
import { Error } from 'pages/error/error'
import { useNavigate, useParams } from 'react-router'
import { useClientSideSort } from 'utils/useClientSideSort'
import { columns } from './deployment-columns'
import styles from './deployments.module.scss'

export const Deployments = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const { deployments, isLoading, isFetching, error } = useDeployments()
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'desc' },
  })

  if (!isLoading && error) {
    return <Error />
  }

  const deployment = deployments?.find((d) => d.id === id)
  const detailsOpen = !!deployment

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
        columns={columns}
        sortable
        sortSettings={sort}
        onSortSettingsChange={setSort}
      />
      {!detailsOpen ? <NewDeploymentDialog /> : null}
      <DeploymentDetailsDialog
        deployment={deployment}
        open={detailsOpen}
        onOpenChange={() => navigate('/deployments')}
      />
    </>
  )
}
