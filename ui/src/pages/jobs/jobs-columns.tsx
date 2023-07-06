import { Job } from 'data-services/models/job'
import { Status } from 'design-system/components/status/types'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Job>[] = [
  {
    id: 'id',
    name: translate(STRING.TABLE_COLUMN_ID),
    renderCell: (item: Job) => (
      <Link
        to={getRoute({
          collection: 'jobs',
          itemId: item.id,
          keepSearchParams: true,
        })}
      >
        <BasicTableCell value={item.idLabel} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'description',
    name: translate(STRING.TABLE_COLUMN_DESCRIPTION),
    renderCell: (item: Job) => <BasicTableCell value={item.description} />,
  },
  {
    id: 'project',
    name: translate(STRING.TABLE_COLUMN_PROJECT),
    renderCell: (item: Job) => <BasicTableCell value={item.project} />,
  },
  {
    id: 'total-captures',
    name: translate(STRING.TABLE_COLUMN_CAPTURES),
    renderCell: (item: Job) => <BasicTableCell value={item.totalImages} />,
  },
  {
    id: 'job-started',
    name: translate(STRING.TABLE_COLUMN_JOB_STARTED),
    renderCell: (item: Job) => <BasicTableCell value={item.jobStarted} />,
  },
  {
    id: 'status',
    name: translate(STRING.TABLE_COLUMN_STATUS),
    renderCell: (item: Job) => {
      const status = (() => {
        switch (item.status) {
          case 0:
          case 1:
            return Status.Warning
          case 2:
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
