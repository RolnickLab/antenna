import { FetchInfo } from 'components/fetch-info/fetch-info'
import { useDeployments } from 'data-services/hooks/useDeployments'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { useClientSideSort } from 'utils/useClientSideSort'
import { columns } from './deployment-columns'
import styles from './deployments.module.scss'

export const Deployments = () => {
  const { deployments, isLoading, isFetching, error } = useDeployments()
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'desc' },
  })

  if (error) {
    return <Error />
  }

  return (
    <>
      {!isLoading && isFetching && (
        <div className={styles.fetchInfoWrapper}>
          <FetchInfo />
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
    </>
  )
}
