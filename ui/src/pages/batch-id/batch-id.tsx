import { useQueues } from 'data-services/hooks/useQueues'
import { Table } from 'design-system/components/table/table/table'
import { columns } from './batch-id-columns'

export const BatchId = () => {
  const { queues, isLoading } = useQueues()

  return <Table items={queues} isLoading={isLoading} columns={columns} />
}
