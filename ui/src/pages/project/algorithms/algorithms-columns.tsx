import { Algorithm } from 'data-services/models/algorithm'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Algorithm>[] = (
  projectId: string
) => [
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
      <Link
        to={APP_ROUTES.ALGORITHM_DETAILS({ projectId, algorithmId: item.id })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'task-type',
    name: 'Task type',
    sortField: 'task_type',
    renderCell: (item: Algorithm) => <BasicTableCell value={item.taskType} />,
  },
  {
    id: 'description',
    name: 'Description',
    sortField: 'description',
    renderCell: (item: Algorithm) => (
      <BasicTableCell value={item.description} />
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
