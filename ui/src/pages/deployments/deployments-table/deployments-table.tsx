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
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

const columns: TableColumn<Deployment>[] = [
  {
    id: 'deployment',
    field: 'name',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortable: true,
    renderCell: (item: Deployment) => (
      <Link to={`/deployments/deployment-id`}>
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'sessions',
    field: 'numEvents',
    name: translate(STRING.TABLE_COLUMN_SESSIONS),
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numEvents} />,
  },
  {
    id: 'images',
    field: 'numImages',
    name: translate(STRING.TABLE_COLUMN_IMAGES),
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    field: 'numDetections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
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
