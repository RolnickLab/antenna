import { Occurrence } from 'data-services/types'
import { useOccurrences } from 'data-services/useOccurrences'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import { Table } from 'design-system/components/table/table/table'
import {
  CellTheme,
  ImageCellTheme,
  OrderBy,
  TableColumn,
} from 'design-system/components/table/types'
import React from 'react'
import { STRING, translate } from 'utils/language'

const columns: TableColumn<Occurrence>[] = [
  {
    id: 'snapshots',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
    sortable: true,
    field: 'timestamp',
    styles: {
      padding: '16px 32px 16px 50px',
    },
    renderCell: (item: Occurrence, rowIndex: number) => {
      const isOddRow = rowIndex % 2 == 0

      return (
        <ImageTableCell
          images={item.images}
          theme={isOddRow ? ImageCellTheme.Default : ImageCellTheme.Light}
        />
      )
    },
  },
  {
    id: 'id',
    name: translate(STRING.TABLE_COLUMN_ID),
    sortable: true,
    field: 'categoryLabel',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.categoryLabel}
        details={[
          item.familyLabel,
          `${translate(STRING.SCORE)}: ${item.categoryScore}`,
        ]}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortable: true,
    field: 'deployment',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.deployment}
        details={[item.deploymentLocation]}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'session',
    name: translate(STRING.TABLE_COLUMN_SESSION),
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.sessionId}
        details={[item.sessionTimespan]}
        theme={CellTheme.Primary}
      />
    ),
  },
  {
    id: 'appearance',
    name: translate(STRING.TABLE_COLUMN_APPEARANCE),
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.appearanceTimespan}
        details={[item.appearanceDuration]}
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
      defaultSortSettings={{
        columnId: 'snapshots',
        orderBy: OrderBy.Descending,
      }}
    ></Table>
  )
}
