import { Job, JobStatus } from 'data-services/models/job'
import { Status } from 'design-system/components/status/types'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { CancelJob } from 'pages/job-details/job-actions/cancel-job'
import { QueueJob } from 'pages/job-details/job-actions/queue-job'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { DeleteJobsDialog } from './delete-jobs-dialog'
import styles from './jobs.module.scss'

export const columns: (projectId: string) => TableColumn<Job>[] = (
  projectId: string
) => [
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
    renderCell: (item: Job) => {
      const status = (() => {
        switch (item.status) {
          case JobStatus.Created:
            return Status.Neutral
          case JobStatus.Pending:
            return Status.Warning
          case JobStatus.Started:
            return Status.Warning
          case JobStatus.Success:
            return Status.Success
          case JobStatus.Retrying:
            return Status.Warning
          case JobStatus.Canceling:
            return Status.Warning
          case JobStatus.Revoked:
            return Status.Error
          case JobStatus.Failed:
            return Status.Error
          default:
            return Status.Error
        }
      })()

      return (
        <StatusTableCell
          label={item.statusLabel}
          status={status}
          details={item.statusDetails}
        />
      )
    },
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Job) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Job) => <BasicTableCell value={item.updatedAt} />,
  },
  {
    id: 'finished-at',
    name: translate(STRING.FIELD_LABEL_FINISHED_AT),
    sortField: 'finished_at',
    renderCell: (item: Job) => <BasicTableCell value={item.finishedAt} />,
  },
  {
    id: 'job-type',
    name: 'Type',
    renderCell: (item: Job) => <BasicTableCell value={item.jobType.name} />,
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Job) => (
      <div className={styles.jobActions}>
        {item.canQueue && <QueueJob jobId={item.id} />}
        {item.canCancel && <CancelJob jobId={item.id} />}
        {item.canDelete && <DeleteJobsDialog id={item.id} />}
      </div>
    ),
  },
]
