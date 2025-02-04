import { API_ROUTES } from 'data-services/constants'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/overview/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/overview/entities/entity-details-dialog'
import styles from 'pages/overview/entities/styles.module.scss'
import { ProcessingServiceDetailsDialog } from 'pages/processing-service-details/processing-service-details-dialog'
import { STRING, translate } from 'utils/language'
import { PopulateProcessingService } from './processing-services-actions'

export const columns: (
  projectId: string
) => TableColumn<ProcessingService>[] = () => [
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
      <BasicTableCell>
        <ProcessingServiceDetailsDialog id={item.id} name={item.name} />
      </BasicTableCell>
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
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.createdAt} />
    ),
  },
  {
    id: 'status',
    name: 'Status',
    renderCell: (item: ProcessingService) => {
      return (
        <StatusTableCell color={item.status.color} label={item.status.label} />
      )
    },
  },
  {
    id: 'last-checked',
    name: translate(STRING.FIELD_LABEL_LAST_CHECKED),
    sortField: 'last_checked',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.lastChecked} />
    ),
  },
  {
    id: 'num-pipelines-added',
    name: translate(STRING.FIELD_LABEL_NUM_PIPELINES_REGISTERED),
    sortField: 'num_PIPELINES_REGISTERED',
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.num_piplines_added} />
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
        {<PopulateProcessingService processingService={item} />}
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
