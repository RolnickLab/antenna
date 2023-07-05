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

export const columns: TableColumn<Deployment>[] = [
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortField: 'name',
    renderCell: (item: Deployment) => (
      <Link
        to={getRoute({
          collection: 'deployments',
          itemId: item.id,
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'sessions',
    name: translate(STRING.TABLE_COLUMN_SESSIONS),
    sortField: 'numEvents',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getRoute({
          collection: 'sessions',
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numEvents} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'images',
    name: translate(STRING.TABLE_COLUMN_IMAGES),
    sortField: 'numImages',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'detections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
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
    name: translate(STRING.TABLE_COLUMN_OCCURRENCES),
    sortField: 'numOccurrences',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getRoute({
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
    name: translate(STRING.TABLE_COLUMN_SPECIES),
    sortField: 'numSpecies',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Deployment) => (
      <Link
        to={getRoute({
          collection: 'species',
          filters: { deployment: item.id },
        })}
      >
        <BasicTableCell value={item.numSpecies} theme={CellTheme.Primary} />
      </Link>
    ),
  },
]
