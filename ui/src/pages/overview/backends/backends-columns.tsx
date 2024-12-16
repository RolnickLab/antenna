import { API_ROUTES } from 'data-services/constants'
import { Backend } from 'data-services/models/backend'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/overview/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/overview/entities/entity-details-dialog'
import styles from 'pages/overview/entities/styles.module.scss'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Backend>[] = () => [
  {
    id: 'id',
    sortField: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: Backend) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'endpoint',
    name: translate(STRING.FIELD_LABEL_ENDPOINT),
    sortField: 'endpoint',
    renderCell: (item: Backend) => <BasicTableCell value={item.endpointUrl} />,
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Backend) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Backend) => <BasicTableCell value={item.updatedAt} />,
  },
  {
    id: 'last-checked',
    name: translate(STRING.FIELD_LABEL_LAST_CHECKED),
    sortField: 'last_checked',
    renderCell: (item: Backend) => <BasicTableCell value={item.lastChecked} />,
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Backend) => (
      <div className={styles.entityActions}>
        {item.canUpdate && (
          <UpdateEntityDialog
            collection={API_ROUTES.BACKENDS}
            entity={item}
            type="backend"
          />
        )}
        {item.canDelete && (
          <DeleteEntityDialog
            collection={API_ROUTES.BACKENDS}
            id={item.id}
            type="backend"
          />
        )}
      </div>
    ),
  },
]
