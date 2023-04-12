import { Deployment } from 'data-services/models/deployment'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Deployment>[] = [
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    sortField: 'name',
    renderCell: (item: Deployment) => (
      <Link to={`/deployments/deployment-id`}>
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
    renderCell: (item: Deployment) => <BasicTableCell value={item.numEvents} />,
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
]
