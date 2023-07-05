import { Occurrence } from 'data-services/models/occurrence'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Occurrence>[] = [
  {
    id: 'snapshots',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
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
    renderCell: (item: Occurrence) => (
      <Link to={getRoute({ collection: 'occurrences', itemId: item.id })}>
        <BasicTableCell
          value={item.determinationLabel}
          details={[`(${item.determinationScore})`]}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    renderCell: (item: Occurrence) => (
      <Link
        to={getRoute({ collection: 'deployments', itemId: item.deploymentId })}
      >
        <BasicTableCell
          value={item.deploymentLabel}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'session',
    name: translate(STRING.TABLE_COLUMN_SESSION),
    renderCell: (item: Occurrence) => (
      <Link to={getRoute({ collection: 'sessions', itemId: item.sessionId })}>
        <BasicTableCell value={item.sessionLabel} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'date',
    name: translate(STRING.TABLE_COLUMN_DATE),
    renderCell: (item: Occurrence) => <BasicTableCell value={item.dateLabel} />,
  },
  {
    id: 'time',
    name: translate(STRING.TABLE_COLUMN_TIME),
    renderCell: (item: Occurrence) => <BasicTableCell value={item.timeLabel} />,
  },
  {
    id: 'duration',
    name: translate(STRING.TABLE_COLUMN_DURATION),
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'detections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
]
