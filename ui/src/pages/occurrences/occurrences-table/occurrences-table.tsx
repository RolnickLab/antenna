import { Occurrence } from 'data-services/types'
import { useOccurrences } from 'data-services/useOccurrences'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import { Table } from 'design-system/components/table/table/table'
import {
  CellTheme,
  OrderBy,
  TableColumn,
} from 'design-system/components/table/types'
import React from 'react'

const columns: TableColumn<Occurrence>[] = [
  {
    id: 'image',
    name: 'Most recent',
    sortable: true,
    field: 'timestamp',
    styles: {
      padding: '16px 32px 16px 50px',
    },
    renderCell: (item: Occurrence) => <ImageTableCell images={item.images} />,
  },
  {
    id: 'id',
    name: 'ID',
    sortable: true,
    field: 'categoryLabel',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.categoryLabel}
        details={item.familyLabel}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'deployment',
    name: 'Deployment',
    sortable: true,
    field: 'deployment',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.deployment}
        details={item.deploymentLocation}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'session',
    name: 'Session',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.sessionId}
        details={item.sessionTimespan}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'appearance',
    name: 'Appearance',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.appearanceTimespan}
        details={item.appearanceDuration}
        theme={CellTheme.Primary}
      />
    ),
  },
]

export const OccurrencesTable = () => {
  const occurrences = useOccurrences()

  return (
    <Table
      items={occurrences}
      columns={columns}
      defaultSortSettings={{ columnId: 'id', orderBy: OrderBy.Descending }}
    ></Table>
  )
}
