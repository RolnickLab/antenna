import { useDeployments } from 'data-services/hooks/useDeployments'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { useClientSideSort } from 'utils/useClientSideSort'
import { columns } from './deployment-columns'

export const Deployments = () => {
  const { deployments, isLoading, error } = useDeployments()
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'desc' },
  })

  if (error) {
    return <Error />
  }

  return (
    <Table
      items={sortedItems}
      isLoading={isLoading}
      columns={columns}
      sortable
      sortSettings={sort}
      onSortSettingsChange={setSort}
    />
  )
}
