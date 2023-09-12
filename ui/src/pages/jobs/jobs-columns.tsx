import { Job, JobStatus } from 'data-services/models/job'
import { Status } from 'design-system/components/status/types'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Job>[] = (
  projectId: string
) => [
  {
    id: 'job',
    name: 'Job',
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
    id: 'project',
    name: translate(STRING.FIELD_LABEL_PROJECT),
    renderCell: (item: Job) => <BasicTableCell value={item.project} />,
  },
  {
    id: 'started-at',
    name: 'Started at',
    renderCell: (item: Job) => <BasicTableCell value={item.startedAt} />,
  },
  {
    id: 'finsihed-at',
    name: 'Finished at',
    renderCell: (item: Job) => <BasicTableCell value={item.finishedAt} />,
  },
  {
    id: 'status',
    name: translate(STRING.FIELD_LABEL_STATUS),
    renderCell: (item: Job) => {
      const status = (() => {
        switch (item.status) {
          case JobStatus.Pending:
            return Status.Neutral
          case JobStatus.Started:
            return Status.Warning
          case JobStatus.Success:
            return Status.Success
          default:
            return Status.Error
        }
      })()

      return (
        <StatusTableCell
          details={item.statusDetails}
          label={item.statusLabel}
          status={status}
        />
      )
    },
  },
]
