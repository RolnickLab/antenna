import { Occurrence } from 'data-services/types'
import { useOccurrences } from 'data-services/useOccurrences'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { Table } from 'design-system/components/table/table/table'
import {
  CellTheme,
  OrderBy,
  TableColumn,
} from 'design-system/components/table/types'
import React from 'react'

const columns: TableColumn<Occurrence>[] = [
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
