import { Collection } from 'data-services/models/collection'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { DeleteEntityDialog } from 'pages/overview/entities/delete-entity-dialog'
import styles from 'pages/overview/entities/styles.module.scss'
import { API_ROUTES } from 'data-services/constants'
import { UpdateEntityDialog } from 'pages/overview/entities/entity-details-dialog'

export const columns: (projectId: string) => TableColumn<Collection>[] = (
  projectId: string
) => [
    {
      id: 'name',
      name: translate(STRING.FIELD_LABEL_NAME),
      sortField: 'name',
      renderCell: (item: Collection) => (
        <Link
          to={APP_ROUTES.COLLECTION_DETAILS({ projectId, collectionId: item.id })}
        >
          <BasicTableCell value={item.name} theme={CellTheme.Primary} />
        </Link>
      ),
    },
    {
      id: 'sampling-method',
      name: translate(STRING.FIELD_LABEL_SAMPLING_METHOD),
      sortField: 'method',
      renderCell: (item: Collection) => (
        <BasicTableCell value={item.methodNameDisplay} details={item.methodDetailsDisplay} />
      ),
    },
    {
      id: 'captures',
      name: translate(STRING.FIELD_LABEL_CAPTURES),
      sortField: 'source_image_count',
      styles: {
        textAlign: TextAlign.Right,
      },
      renderCell: (item: Collection) => <BasicTableCell value={item.numImages} />,
    },
    {
      id: 'created-at',
      name: translate(STRING.FIELD_LABEL_CREATED_AT),
      sortField: 'created_at',
      renderCell: (item: Collection) => <BasicTableCell value={item.createdAt} />,
    },
    {
      id: 'updated-at',
      name: translate(STRING.FIELD_LABEL_UPDATED_AT),
      sortField: 'updated_at',
      renderCell: (item: Collection) => <BasicTableCell value={item.updatedAt} />,
    },
    {
      id: 'actions',
      name: '',
      styles: {
        padding: '16px',
        width: '100%',
      },
      renderCell: (item: Collection) => (
        <div className={styles.entityActions}>
          {item.canUpdate && (
            <UpdateEntityDialog
              collection={API_ROUTES.COLLECTIONS}
              entity={item}
              type="collection" />
          )}
          {item.canDelete && (
            <DeleteEntityDialog
              collection={API_ROUTES.COLLECTIONS}
              id={item.id}
              type="collection"
            />
          )}
        </div>
      ),
    },
  ]
