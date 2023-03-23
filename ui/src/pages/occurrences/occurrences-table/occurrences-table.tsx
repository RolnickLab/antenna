import { Occurrence } from 'data-services/models/occurrence'
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
import { Link } from 'react-router-dom'
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
      <Link to={`/occurrences/occurrence-id`}>
        <BasicTableCell
          value={item.categoryLabel}
          details={[
            item.familyLabel,
            `${translate(STRING.SCORE)}: ${item.categoryScore}`,
          ]}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortable: true,
    field: 'deployment',
    renderCell: (item: Occurrence) => (
      <Link to={`/deployments/deployment-id`}>
        <BasicTableCell
          value={item.deployment}
          details={[item.deploymentLocation]}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'session',
    name: translate(STRING.TABLE_COLUMN_SESSION),
    renderCell: (item: Occurrence) => (
      <Link to={`/sessions/session-id`}>
        <BasicTableCell
          value={item.sessionId}
          details={[item.sessionTimespan]}
          theme={CellTheme.Primary}
        />
      </Link>
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

interface OccurrencesTableProps {
  occurrences: Occurrence[]
  isLoading: boolean
}

export const OccurrencesTable = ({
  occurrences,
  isLoading,
}: OccurrencesTableProps) => (
  <Table
    items={occurrences}
    isLoading={isLoading}
    columns={columns}
    defaultSortSettings={{
      columnId: 'snapshots',
      orderBy: OrderBy.Descending,
    }}
  ></Table>
)
