import { Session } from 'data-services/models/session'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Session>[] = [
  {
    id: 'snapshots',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
    styles: {
      padding: '16px 32px 16px 50px',
    },
    renderCell: (item: Session, rowIndex: number) => {
      const isOddRow = rowIndex % 2 == 0

      return (
        <ImageTableCell
          images={item.exampleCaptures}
          theme={isOddRow ? ImageCellTheme.Default : ImageCellTheme.Light}
        />
      )
    },
  },
  {
    id: 'session',
    name: translate(STRING.TABLE_COLUMN_ID),
    sortField: 'id',
    renderCell: (item: Session) => (
      <Link to={`/sessions/${item.id}`}>
        <BasicTableCell value={item.idLabel} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    renderCell: (item: Session) => (
      <Link to={`/deployments/${item.deploymentId}`}>
        <BasicTableCell
          value={item.deploymentLabel}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'date',
    name: translate(STRING.TABLE_COLUMN_DATE),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.datespanLabel} />
    ),
  },
  {
    id: 'time',
    name: translate(STRING.TABLE_COLUMN_TIME),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.timespanLabel} />
    ),
  },
  {
    id: 'duration',
    name: translate(STRING.TABLE_COLUMN_DURATION),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'images',
    name: translate(STRING.TABLE_COLUMN_IMAGES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
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
    renderCell: (item: Session) => <BasicTableCell value={item.tempLabel} />,
  },
]
