import { useQueues } from 'data-services/hooks/useQueues'
import { Table } from 'design-system/components/table/table/table'
import { Error } from 'pages/error/error'
import { columns } from './batch-id-columns'

export const BatchId = () => {
  const { queues, isLoading, error } = useQueues()

  if (error) {
    return <Error details={error} />
  }

  return <Table items={queues} isLoading={isLoading} columns={columns} />
}
