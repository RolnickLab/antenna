import { API_ROUTES } from 'data-services/constants'
import { Job } from 'data-services/models/job'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { DateTableCell } from 'design-system/components/table/date-table-cell/date-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { CancelJob } from 'pages/job-details/job-actions/cancel-job'
import { QueueJob } from 'pages/job-details/job-actions/queue-job'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './jobs.module.scss'

export const columns = ({
  projectId,
  showActions,
}: {
  projectId: string
  showActions?: boolean
}): TableColumn<Job>[] => [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Job) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.JOB_DETAILS({ projectId, jobId: item.id }),
          keepSearchParams: true,
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'status',
    name: translate(STRING.FIELD_LABEL_STATUS),
    tooltip: translate(STRING.TOOLTIP_STATUS),
    sortField: 'status',
    renderCell: (item: Job) => (
      <StatusTableCell
        color={item.status.color}
        details={item.progress.label}
        label={item.status.label}
      />
    ),
  },
  {
    id: 'job-type',
    name: 'Type',
    renderCell: (item: Job) => <BasicTableCell value={item.type.label} />,
  },
  {
    id: 'deployment',
    sortField: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    renderCell: (item: Job) =>
      item.deployment ? (
        <Link
          to={APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId,
            deploymentId: item.deployment?.id,
          })}
        >
          <BasicTableCell
            value={item.deployment?.name}
            theme={CellTheme.Primary}
          />
        </Link>
      ) : (
        <></>
      ),
  },
  {
    id: 'pipeline',
    sortField: 'pipeline',
    name: translate(STRING.FIELD_LABEL_PIPELINE),
    renderCell: (item: Job) => <BasicTableCell value={item.pipeline?.name} />,
  },
  {
    id: 'source-image',
    name: translate(STRING.FIELD_LABEL_CAPTURE),
    renderCell: (item: Job) =>
      item.sourceImage?.sessionId ? (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.SESSION_DETAILS({
              projectId: projectId as string,
              sessionId: item.sourceImage.sessionId,
            }),
            filters: {
              capture: item.sourceImage.id,
            },
          })}
        >
          <BasicTableCell
            value={item.sourceImage?.label}
            theme={CellTheme.Primary}
          />
        </Link>
      ) : (
        <></>
      ),
  },
  {
    id: 'source-image-collection',
    sortField: 'source_image_collection',
    name: translate(STRING.FIELD_LABEL_CAPTURE_SET),
    renderCell: (item: Job) => (
      <BasicTableCell value={item.sourceImages?.name} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Job) => <DateTableCell date={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Job) => <DateTableCell date={item.updatedAt} />,
  },
  {
    id: 'started-at',
    name: translate(STRING.FIELD_LABEL_STARTED_AT),
    sortField: 'started_at',
    renderCell: (item: Job) => <DateTableCell date={item.startedAt} />,
  },
  {
    id: 'finished-at',
    name: translate(STRING.FIELD_LABEL_FINISHED_AT),
    sortField: 'finished_at',
    renderCell: (item: Job) => <DateTableCell date={item.finishedAt} />,
  },
  ...(showActions
    ? [
        {
          id: 'actions',
          name: '',
          sticky: true,
          renderCell: (item: Job) => (
            <div className={styles.jobActions}>
              {item.canQueue && <QueueJob jobId={item.id} />}
              {item.canCancel && <CancelJob jobId={item.id} />}
              {item.canDelete && (
                <DeleteEntityDialog
                  collection={API_ROUTES.JOBS}
                  id={item.id}
                  type={translate(STRING.ENTITY_TYPE_JOB)}
                />
              )}
            </div>
          ),
        },
      ]
    : []),
]
