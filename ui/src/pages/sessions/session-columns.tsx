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
    name: translate(STRING.FIELD_LABEL_SNAPSHOTS),
    styles: {
      textAlign: TextAlign.Center,
    },
    renderCell: (item: Session) => {
      const detailsRoute = APP_ROUTES.SESSION_DETAILS({
        projectId,
        sessionId: item.id,
      })

      return (
        <ImageTableCell
          images={item.exampleCaptures}
          total={item.numImages}
          to={detailsRoute}
          theme={ImageCellTheme.Light}
        />
      )
    },
  },
  {
    id: 'session',
    sortField: 'start',
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
    sortField: 'deployment',
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
    name: translate(STRING.FIELD_LABEL_DATE),
    sortField: 'start',
    renderCell: (item: Session) => (
      <BasicTableCell value={item.datespanLabel} />
    ),
  },
  {
    id: 'time',
    name: translate(STRING.FIELD_LABEL_TIME),
    sortField: 'start__time',
    renderCell: (item: Session) => (
      <BasicTableCell value={item.timespanLabel} />
    ),
  },
  {
    id: 'duration',
    name: translate(STRING.FIELD_LABEL_DURATION),
    sortField: 'duration',
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
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'species',
    name: translate(STRING.FIELD_LABEL_TAXA),
    sortField: 'taxa_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Session) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.TAXA({ projectId }),
          filters: { event: item.id },
        })}
      >
        <BasicTableCell value={item.numTaxa} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
]
