import { Job } from 'data-services/models/job'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import {
  CellStatus,
  CellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Job>[] = [
  {
    id: 'id',
    name: translate(STRING.TABLE_COLUMN_ID),
    renderCell: (item: Job) => (
      <Link to={`/jobs/${item.id}`}>
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
    id: 'total-images',
    name: translate(STRING.TABLE_COLUMN_IMAGES),
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
            return CellStatus.Warning
          case 2:
            return CellStatus.Success
          default:
            return CellStatus.Error
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
