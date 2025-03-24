import classNames from 'classnames'
import { API_ROUTES } from 'data-services/constants'
import { Export } from 'data-services/models/export'
import { StatusBar } from 'design-system/components/status/status-bar'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { DownloadIcon } from 'lucide-react'
import { buttonVariants } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { DeleteEntityDialog } from '../entities/delete-entity-dialog'

export const columns: (projectId: string) => TableColumn<Export>[] = (
  projectId: string
) => [
  {
    id: 'name',
    sortField: 'format',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Export) => <BasicTableCell value={item.type.label} />,
  },
  {
    id: 'source-image-collection',
    name: translate(STRING.FIELD_LABEL_SOURCE_IMAGES),
    renderCell: (item: Export) =>
      item.sourceImages ? (
        <Link
          to={APP_ROUTES.COLLECTION_DETAILS({
            projectId,
            collectionId: item.sourceImages.id,
          })}
        >
          <BasicTableCell
            value={item.sourceImages.name}
            theme={CellTheme.Primary}
          />
        </Link>
      ) : (
        <></>
      ),
  },
  {
    id: 'status',
    name: translate(STRING.FIELD_LABEL_STATUS),
    renderCell: (item: Export) => {
      if (!item.job) {
        return <></>
      }

      return (
        <StatusTableCell
          color={item.job.status.color}
          label={item.job.status.label}
        />
      )
    },
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Export) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Export) => <BasicTableCell value={item.updatedAt} />,
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
        <div className="flex items-center justify-end gap-2 p-4">
          {item.job.progress.value !== 1 ? (
            <div className="w-min">
              <StatusBar
                color={item.job.status.color}
                progress={item.job.progress.value}
              />
            </div>
          ) : (
            <a
              href={item.fileUrl}
              download={item.fileUrl}
              className={classNames(
                buttonVariants({
                  size: 'small',
                  variant: 'outline',
                }),
                '!w-auto !rounded-full'
              )}
            >
              <DownloadIcon className="w-4 h-4" />
              <span>Download</span>
            </a>
          )}
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
