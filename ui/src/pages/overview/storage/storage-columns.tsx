import { API_ROUTES } from 'data-services/constants'
import { StorageSource } from 'data-services/models/storage'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  TableColumn,
  TextAlign
} from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/overview/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/overview/entities/entity-details-dialog'
import styles from 'pages/overview/entities/styles.module.scss'
import { STRING, translate } from 'utils/language'
import { SyncStorage } from './storage-actions'


export const columns: (projectId: string) => TableColumn<StorageSource>[] = (
  projectId: string
) => [
    {
      id: 'name',
      name: translate(STRING.FIELD_LABEL_NAME),
      sortField: 'name',
      renderCell: (item: StorageSource) => (
        <BasicTableCell value={item.name} />
      ),
    },
    {
      id: 'description',
      name: translate(STRING.FIELD_LABEL_DESCRIPTION),
      sortField: 'description',
      renderCell: (item: StorageSource) => (
        <BasicTableCell value={item.description} />
      ),
    },
    {
      id: 'total_size',
      name: 'Total Size', // 'Total Size
      sortField: 'total_size_indexed',
      styles: {
        textAlign: TextAlign.Right,
      },
      renderCell: (item: StorageSource) => <BasicTableCell value={item.totalSizeDisplay} />,
    },
    {
      id: 'total_files',
      name: 'Total Files', // 'Total Files
      sortField: 'total_files_indexed',
      styles: {
        textAlign: TextAlign.Right,
      },
      renderCell: (item: StorageSource) => <BasicTableCell value={item.totalFiles} />,
    },
    {
      id: 'deployments',
      name: translate(STRING.NAV_ITEM_DEPLOYMENTS),
      sortField: 'num_deployments',
      styles: {
        textAlign: TextAlign.Right,
      },
      renderCell: (item: StorageSource) => <BasicTableCell value={item.deploymentsCount} />,
    },
    {
      id: 'updated-at',
      name: translate(STRING.FIELD_LABEL_UPDATED_AT),
      sortField: 'updated_at',
      renderCell: (item: StorageSource) => <BasicTableCell value={item.updatedAt} />,
    },
    {
      id: 'storage-actions',
      name: '',
      styles: {
        padding: '16px',
        width: '100%',
      },
      renderCell: (item: StorageSource) => (
        <div className={styles.entityActions}>
          {item.canUpdate && (
            <SyncStorage storageId={item.id} />
          )}
        </div>
      ),
    },
    {
      id: 'actions',
      name: '',
      styles: {
        padding: '16px',
        width: '100%',
      },
      renderCell: (item: StorageSource) => (
        <div className={styles.entityActions}>
          {item.canUpdate && (
            <UpdateEntityDialog
              collection={API_ROUTES.STORAGE}
              entity={item}
              type="storage" />
          )}
          {item.canDelete && (
            <DeleteEntityDialog
              collection={API_ROUTES.STORAGE}
              id={item.id}
              type="storage"
            />
          )}
        </div>
      ),
    },
  ]
