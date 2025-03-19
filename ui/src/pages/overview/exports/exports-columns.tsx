import classNames from 'classnames'
import { API_ROUTES } from 'data-services/constants'
import { Export } from 'data-services/models/export'
import { StatusBar } from 'design-system/components/status/status-bar'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { DownloadIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { DeleteEntityDialog } from '../entities/delete-entity-dialog'

export const columns: (projectId: string) => TableColumn<Export>[] = (
  projectId: string
) => [
  {
    id: 'id',
    sortField: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: Export) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'type',
    name: translate(STRING.FIELD_LABEL_TYPE),
    renderCell: (item: Export) => <BasicTableCell value={item.typeLabel} />,
  },
  {
    id: 'progress',
    name: 'Progress',
    renderCell: (item: Export) => {
      if (!item.job) {
        return <></>
      }

      return (
        <BasicTableCell>
          <StatusBar
            color={item.job.status.color}
            progress={item.job.progress.value}
          />
        </BasicTableCell>
      )
    },
  },
  {
    id: 'job',
    name: translate(STRING.FIELD_LABEL_JOB),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Export) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.JOB_DETAILS({ projectId, jobId: item.job.id }),
        })}
      >
        <BasicTableCell
          value={`Job ${item.job.id}`}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'result',
    name: translate(STRING.FIELD_LABEL_RESULT),
    renderCell: (item: Export) => {
      if (!item.fileUrl) {
        return <></>
      }

      return (
        <BasicTableCell>
          <div className="flex items-center gap-4">
            <a
              href={item.fileUrl}
              download={item.fileUrl}
              className={classNames(
                buttonVariants({
                  size: 'small',
                  variant: 'outline',
                }),
                '!rounded-full'
              )}
            >
              <DownloadIcon className="w-4 h-4" />
              <span>Download</span>
            </a>
          </div>
        </BasicTableCell>
      )
    },
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Export) => {
      if (!item.canDelete) {
        return <></>
      }

      return (
        <div className="flex items-center justify-end p-4">
          <DeleteEntityDialog
            collection={API_ROUTES.EXPORTS}
            id={item.id}
            type="export"
          />
        </div>
      )
    },
  },
]
