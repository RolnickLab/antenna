import { API_ROUTES } from 'data-services/constants'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { DateTableCell } from 'design-system/components/table/date-table-cell/date-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/project/entities/entity-details-dialog'
import styles from 'pages/project/entities/styles.module.scss'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { PopulateProcessingService } from './processing-services-actions'

export const columns = ({
  projectId,
  showActions,
}: {
  projectId: string
  showActions?: boolean
}): TableColumn<ProcessingService>[] => [
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
    id: 'status',
    name: 'Status',
    renderCell: (item: ProcessingService) => (
      <StatusTableCell
        color={item.status.color}
        details={'Last checked ' + item.lastChecked}
        label={item.status.label}
      />
    ),
  },
  {
    id: 'num-pipelines-added',
    name: translate(STRING.FIELD_LABEL_NUM_PIPELINES_REGISTERED),
    renderCell: (item: ProcessingService) => (
      <BasicTableCell value={item.numPiplinesAdded} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: ProcessingService) => (
      <DateTableCell date={item.createdAt} />
    ),
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: ProcessingService) => (
      <DateTableCell date={item.updatedAt} />
    ),
  },
  ...(showActions
    ? [
        {
          id: 'actions',
          name: '',
          sticky: true,
          renderCell: (item: ProcessingService) => (
            <div className={styles.entityActions}>
              {item.canDelete && (
                <DeleteEntityDialog
                  collection={API_ROUTES.PROCESSING_SERVICES}
                  id={item.id}
                  type="service"
                />
              )}
              {item.canUpdate && (
                <>
                  <UpdateEntityDialog
                    collection={API_ROUTES.PROCESSING_SERVICES}
                    entity={item}
                    type="service"
                  />
                  <PopulateProcessingService processingService={item} />
                </>
              )}
            </div>
          ),
        },
      ]
    : []),
]
