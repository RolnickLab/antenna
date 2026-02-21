import { API_ROUTES } from 'data-services/constants'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/project/entities/entity-details-dialog'
import styles from 'pages/project/entities/styles.module.scss'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { PopulateProcessingService } from './processing-services-actions'

export const columns: (
  projectId: string,
  canCreate?: boolean
) => TableColumn<ProcessingService>[] = (
  projectId: string,
  canCreate?: boolean
) => [
  {
    id: 'id',
    sortField: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: ProcessingService) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'name',
    sortField: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: ProcessingService) => (
      <Link
        to={APP_ROUTES.PROCESSING_SERVICE_DETAILS({
          projectId,
          processingServiceId: item.id,
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'endpoint',
    name: translate(STRING.FIELD_LABEL_ENDPOINT),
    sortField: 'endpoint',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.endpointUrl} />
    ),
  },
  {
    id: 'status',
    name: 'Status',
    renderCell: (item: ProcessingService) => (
      <StatusTableCell
        color={item.status.color}
        details={'Last seen ' + item.lastSeen}
        label={item.status.label}
      />
    ),
  },
  {
    id: 'num-pipelines-added',
    name: translate(STRING.FIELD_LABEL_NUM_PIPELINES_REGISTERED),
    sortField: 'num_PIPELINES_REGISTERED',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.numPiplinesAdded} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.createdAt} />
    ),
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.updatedAt} />
    ),
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: ProcessingService) => (
      <div className={styles.entityActions}>
        {canCreate && <PopulateProcessingService processingService={item} />}
        {item.canUpdate && (
          <UpdateEntityDialog
            collection={API_ROUTES.PROCESSING_SERVICES}
            entity={item}
            type="service"
          />
        )}
        {item.canDelete && (
          <DeleteEntityDialog
            collection={API_ROUTES.PROCESSING_SERVICES}
            id={item.id}
            type="service"
          />
        )}
      </div>
    ),
  },
]
