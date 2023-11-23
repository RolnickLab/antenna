import { Entity } from 'data-services/models/entity'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { STRING, translate } from 'utils/language'
import { DeleteEntityDialog } from './delete-entity-dialog'
import styles from './styles.module.scss'

export const columns: (collection: string) => TableColumn<Entity>[] = (
  collection: string
) => [
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
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Entity) => (
      <div className={styles.entityActions}>
        {item.canDelete && (
          <DeleteEntityDialog collection={collection} id={item.id} />
        )}
      </div>
    ),
  },
]
