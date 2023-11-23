import { Entity } from 'data-services/models/entity'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Entity>[] = () => [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Entity) => <BasicTableCell value={item.name} />,
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Entity) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Entity) => <BasicTableCell value={item.updatedAt} />,
  },
]
