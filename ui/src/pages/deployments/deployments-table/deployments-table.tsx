import { Deployment } from 'data-services/types'
import { useDeployments } from 'data-services/useDeployments'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { Table } from 'design-system/components/table/table/table'
import {
  CellTheme,
  OrderBy,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import React from 'react'

const columns: TableColumn<Deployment>[] = [
  {
    id: 'deployment',
    field: 'name',
    name: 'Deployment',
    sortable: true,
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.name} theme={CellTheme.Primary} />
    ),
  },
  {
    id: 'sessions',
    field: 'numEvents',
    name: 'Sessions',
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    field: 'numSourceImages',
    name: 'Images',
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.numSourceImages} />
    ),
  },
  {
    id: 'detections',
    field: 'numDetections',
    name: 'Detections',
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
]

export const DeploymentsTable = () => {
  const deployments = useDeployments()

  return (
    <Table
      items={deployments}
      columns={columns}
      defaultSortSettings={{
        columnId: 'deployment',
        orderBy: OrderBy.Descending,
      }}
    ></Table>
  )
}
