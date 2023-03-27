import { useDeployments } from 'data-services/hooks/useDeployments'
import { SimpleTable } from 'design-system/components/table/table/simple-table'
import React from 'react'
import { columns } from './deployment-columns'

export const Deployments = () => {
  const { deployments, isLoading } = useDeployments()

  return (
    <SimpleTable
      items={deployments}
      isLoading={isLoading}
      columns={columns}
      defaultSortSettings={{
        columnId: 'deployment',
        orderBy: 'desc',
      }}
    />
  )
}
