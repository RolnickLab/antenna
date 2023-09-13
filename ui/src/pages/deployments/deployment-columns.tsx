import { Deployment } from 'data-services/models/deployment'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Deployment>[] = (
  projectId: string
) => [
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    sortField: 'name',
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId,
            deploymentId: item.id,
          }),
          keepSearchParams: true,
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'sessions',
    name: translate(STRING.FIELD_LABEL_SESSIONS),
    sortField: 'numEvents',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SESSIONS({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numEvents} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    sortField: 'numImages',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'numOccurrences',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'species',
    name: translate(STRING.FIELD_LABEL_SPECIES),
    sortField: 'numSpecies',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SPECIES({ projectId }),
          filters: { occurrences__deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numSpecies} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'firstDate',
    name: translate(STRING.FIELD_LABEL_FIRST_DATE),
    sortField: 'firstDate',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.firstDate} />,
  },
  {
    id: 'lastDate',
    name: translate(STRING.FIELD_LABEL_LAST_DATE),
    sortField: 'lastDate',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.lastDate} />,
  },
]
