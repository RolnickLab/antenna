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
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Session>[] = (
  projectId: string
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_MOST_RECENT),
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
    name: translate(STRING.FIELD_LABEL_SESSION),
    renderCell: (item: Session) => (
      <Link to={APP_ROUTES.SESSION_DETAILS({ projectId, sessionId: item.id })}>
        <BasicTableCell value={item.label} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    renderCell: (item: Session) => (
      <Link
        to={APP_ROUTES.DEPLOYMENT_DETAILS({
          projectId,
          deploymentId: item.deploymentId,
        })}
      >
        <BasicTableCell
          value={item.deploymentLabel}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'date',
    sortField: 'start',
    name: translate(STRING.FIELD_LABEL_DATE),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.datespanLabel} />
    ),
  },
  {
    id: 'time',
    name: translate(STRING.FIELD_LABEL_TIME),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.timespanLabel} />
    ),
  },
  {
    id: 'duration',
    sortField: 'duration',
    name: translate(STRING.FIELD_LABEL_DURATION),
    renderCell: (item: Session) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    sortField: 'captures_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    name: translate(STRING.FIELD_LABEL_DETECTIONS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'occurrences_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { event: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'species',
    name: translate(STRING.FIELD_LABEL_SPECIES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SPECIES({ projectId }),
          filters: { occurrences__event: item.id },
        })}
      >
        <BasicTableCell value={item.numSpecies} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'avg-temp',
    name: translate(STRING.FIELD_LABEL_AVG_TEMP),
    renderCell: (item: Session) => <BasicTableCell value={item.tempLabel} />,
  },
]
