import { Algorithm } from 'data-services/models/algorithm'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { AlgorithmDetailsDialog } from 'pages/algorithm-details/algorithm-details-dialog'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Algorithm>[] = () => [
  {
    id: 'id',
    sortField: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: Algorithm) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Algorithm) => (
      <BasicTableCell>
        <AlgorithmDetailsDialog id={item.id} name={item.name} />
      </BasicTableCell>
    ),
  },
  {
    id: 'task-type',
    name: 'Task Type',
    sortField: 'task_type',
    renderCell: (item: Algorithm) => <BasicTableCell value={item.taskType} />,
  },
  {
    id: 'uri',
    name: 'URI',
    sortField: 'uri',
    renderCell: (item: Algorithm) => <BasicTableCell value={item.uri} />,
  },
  {
    id: 'category-map-id',
    name: 'Category Map ID',
    sortField: 'category_map',
    renderCell: (item: Algorithm) => (
      <Link to={item.categoryMapURI}>
        <BasicTableCell value={item.categoryMapID} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Algorithm) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Algorithm) => <BasicTableCell value={item.updatedAt} />,
  },
]
