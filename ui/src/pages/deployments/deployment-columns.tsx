import { Deployment } from 'data-services/models/deployment'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
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
        to={getRoute({
          projectId,
          collection: 'deployments',
          itemId: item.id,
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
        to={getRoute({
          projectId,
          collection: 'sessions',
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
    id: 'detections',
    name: translate(STRING.FIELD_LABEL_DETECTIONS),
    sortField: 'numDetections',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <BasicTableCell value={item.numDetections} />
    ),
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
        to={getRoute({
          projectId,
          collection: 'occurrences',
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
        to={getRoute({
          projectId,
          collection: 'species',
          filters: { occurrences__deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numSpecies} theme={CellTheme.Primary} />
      </Link>
    ),
  },
]
