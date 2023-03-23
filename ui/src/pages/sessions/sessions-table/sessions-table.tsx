import { Session } from 'data-services/types'
import { useSessions } from 'data-services/useSessions'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import { Table } from 'design-system/components/table/table/table'
import {
  CellTheme,
  ImageCellTheme,
  OrderBy,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import React from 'react'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Session>[] = [
  {
    id: 'snapshots',
    field: 'timestamp',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
    sortable: true,
    styles: {
      padding: '16px 32px 16px 50px',
    },
    renderCell: (item: Session, rowIndex: number) => {
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
    id: 'session',
    field: 'id',
    name: translate(STRING.TABLE_COLUMN_SESSION),
    sortable: true,
    renderCell: (item: Session) => (
      <Link to={`/sessions/session-id`}>
        <BasicTableCell value={item.id} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'deployment',
    field: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortable: true,
    renderCell: (item: Session) => (
      <Link to={`/deployments/deployment-id`}>
        <BasicTableCell value={item.deployment} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'date',
    name: translate(STRING.TABLE_COLUMN_DATE),
    renderCell: (item: Session) => <BasicTableCell value={item.datespan} />,
  },
  {
    id: 'time',
    name: translate(STRING.TABLE_COLUMN_TIME),
    renderCell: (item: Session) => <BasicTableCell value={item.timespan} />,
  },
  {
    id: 'duration',
    field: 'durationMinutes',
    name: translate(STRING.TABLE_COLUMN_DURATION),
    sortable: true,
    renderCell: (item: Session) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'images',
    field: 'numImages',
    name: translate(STRING.TABLE_COLUMN_IMAGES),
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    field: 'numDetections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
    sortable: true,
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.TABLE_COLUMN_OCCURRENCES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <BasicTableCell value={item.numOccurrences} />
    ),
  },
  {
    id: 'species',
    name: translate(STRING.TABLE_COLUMN_SPECIES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => <BasicTableCell value={item.numSpecies} />,
  },
  {
    id: 'avg-temp',
    name: translate(STRING.TABLE_COLUMN_AVG_TEMP),
    renderCell: (item: Session) => <BasicTableCell value={item.avgTemp} />,
  },
]

interface SessionsTableProps {
  columnSettings: {
    [id: string]: boolean
  }
}

export const SessionsTable = ({ columnSettings }: SessionsTableProps) => {
  const sessions = useSessions()
  const activeColumns = columns.filter((column) => columnSettings[column.id])

  return (
    <Table
      items={sessions}
      columns={activeColumns}
      defaultSortSettings={{
        columnId: 'snapshots',
        orderBy: OrderBy.Descending,
      }}
    ></Table>
  )
}
