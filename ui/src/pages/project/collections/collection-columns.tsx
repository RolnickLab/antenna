import { API_ROUTES } from 'data-services/constants'
import { Collection } from 'data-services/models/collection'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/project/entities/entity-details-dialog'
import styles from 'pages/project/entities/styles.module.scss'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { PopulateCollection } from './collection-actions'
import { SERVER_SAMPLING_METHODS } from './constants'

export const columns: (projectId: string) => TableColumn<Collection>[] = (
  projectId: string
) => [
  {
    id: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    sortField: 'id',
    renderCell: (item: Collection) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Collection) => <BasicTableCell value={item.name} />,
  },
  {
    id: 'settings',
    name: 'Settings',
    renderCell: (item: Collection) => (
      <BasicTableCell
        value={item.settingsDisplay}
        details={item.settingsDetailsDisplay}
      />
    ),
  },
  {
    id: 'status',
    name: 'Latest job status',
    renderCell: (item: Collection) => {
      if (!item.currentJob) {
        return <></>
      }

      return (
        <StatusTableCell
          color={item.currentJob.status.color}
          details={item.currentJob.type.label}
          label={item.currentJob.status.label}
        />
      )
    },
  },
  {
    id: 'jobs',
    name: translate(STRING.FIELD_LABEL_JOBS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.JOBS({ projectId }),
          filters: { source_image_collection: item.id },
        })}
      >
        <BasicTableCell value={item.numJobs} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'captures',
    name: 'Captures',
    sortField: 'source_images_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.CAPTURES({ projectId }),
          filters: { collections: item.id },
        })}
      >
        <BasicTableCell value={item.numImages} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'captures-with-detections',
    name: translate(STRING.FIELD_LABEL_CAPTURES_WITH_DETECTIONS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => (
      <BasicTableCell value={item.numImagesWithDetectionsLabel} />
    ),
  },
  {
    id: 'total-processed-captures',
    name: translate(STRING.FIELD_LABEL_TOTAL_PROCESSED_CAPTURES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => (
      <BasicTableCell value={item.numImagesProccessed} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'occurrences_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { collection: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'taxa',
    name: translate(STRING.FIELD_LABEL_TAXA),
    sortField: 'taxa_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => <BasicTableCell value={item.numTaxa} />,
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
        {item.canPopulate && <PopulateCollection collection={item} />}
        {item.canUpdate && SERVER_SAMPLING_METHODS.includes(item.method) && (
          <UpdateEntityDialog
            collection={API_ROUTES.COLLECTIONS}
            entity={item}
            type="collection"
          />
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
