import { useDeployments } from 'data-services/hooks/useDeployments'
import { Table } from 'design-system/components/table/table/table'
import { useClientSideSort } from 'utils/useClientSideSort'
import { columns } from './deployment-columns'

export const Deployments = () => {
  const { deployments, isLoading } = useDeployments()
  const { sortedItems, sort, setSort } = useClientSideSort({
    items: deployments,
    defaultSort: { field: 'name', order: 'desc' },
  })

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
