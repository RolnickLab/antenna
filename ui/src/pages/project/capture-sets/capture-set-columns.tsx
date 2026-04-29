import { FormMessage } from 'components/form/layout/layout'
import { API_ROUTES } from 'data-services/constants'
import { CaptureSet } from 'data-services/models/capture-set'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { DateTableCell } from 'design-system/components/table/date-table-cell/date-table-cell'
import { StatusTableCell } from 'design-system/components/table/status-table-cell/status-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Toolbar } from 'design-system/components/toolbar'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/project/entities/entity-details-dialog'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { SERVER_SAMPLING_METHODS } from './constants'
import { PopulateCaptureSet } from './populate-capture-set'

export const columns = ({
  projectId,
}: {
  projectId: string
}): TableColumn<CaptureSet>[] => [
  {
    id: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    sortField: 'id',
    renderCell: (item: CaptureSet) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: CaptureSet) => <BasicTableCell value={item.name} />,
  },
  {
    id: 'settings',
    name: 'Settings',
    renderCell: (item: CaptureSet) => (
      <BasicTableCell
        value={item.settingsDisplay}
        details={item.settingsDetailsDisplay}
      />
    ),
  },
  {
    id: 'status',
    name: 'Latest job status',
    tooltip: translate(STRING.TOOLTIP_LATEST_JOB_STATUS, {
      type: translate(STRING.ENTITY_TYPE_CAPTURE_SET),
    }),
    renderCell: (item: CaptureSet) => {
      if (item.currentJob) {
        return (
          <StatusTableCell
            color={item.currentJob.status.color}
            details={item.currentJob.type.label}
            label={item.currentJob.status.label}
          />
        )
      }

      if (item.canPopulate && item.numImages === 0) {
        return (
          <BasicTableCell>
            <PopulateCaptureSet captureSet={item} />
          </BasicTableCell>
        )
      }

      return <></>
    },
  },
  {
    id: 'jobs',
    name: translate(STRING.FIELD_LABEL_JOBS),
    tooltip: translate(STRING.TOOLTIP_JOB),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: CaptureSet) => {
      return (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.JOBS({ projectId }),
            filters: { source_image_collection: item.id },
          })}
        >
          <BasicTableCell value={item.numJobs} theme={CellTheme.Bubble} />
        </Link>
      )
    },
  },
  {
    id: 'captures',
    name: 'Captures',
    tooltip: translate(STRING.TOOLTIP_CAPTURE),
    sortField: 'source_images_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: CaptureSet) => {
      if (item.canPopulate && item.numImages === 0) {
        return (
          <BasicTableCell>
            <FormMessage
              message={translate(STRING.MESSAGE_CAPTURE_SET_EMPTY)}
              theme="warning"
              withIcon
            />
          </BasicTableCell>
        )
      }

      return (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.CAPTURES({ projectId }),
            filters: { collections: item.id },
          })}
        >
          <BasicTableCell value={item.numImages} theme={CellTheme.Bubble} />
        </Link>
      )
    },
  },
  {
    id: 'captures-with-detections',
    name: translate(STRING.FIELD_LABEL_CAPTURES_WITH_DETECTIONS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: CaptureSet) => (
      <BasicTableCell value={item.numImagesWithDetectionsLabel} />
    ),
  },
  {
    id: 'total-processed-captures',
    name: translate(STRING.FIELD_LABEL_TOTAL_PROCESSED_CAPTURES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: CaptureSet) => (
      <BasicTableCell value={item.numImagesProcessedLabel} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    tooltip: translate(STRING.TOOLTIP_OCCURRENCE),
    sortField: 'occurrences_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: CaptureSet) => (
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
    renderCell: (item: CaptureSet) => <BasicTableCell value={item.numTaxa} />,
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: CaptureSet) => <DateTableCell date={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: CaptureSet) => <DateTableCell date={item.updatedAt} />,
  },
  {
    id: 'actions',
    name: '',
    sticky: true,
    renderCell: (item: CaptureSet) => (
      <Toolbar>
        {item.canPopulate && (
          <PopulateCaptureSet captureSet={item} compact variant="ghost" />
        )}
        {item.canUpdate && SERVER_SAMPLING_METHODS.includes(item.method) && (
          <UpdateEntityDialog
            collection={API_ROUTES.CAPTURE_SETS}
            entity={item}
            type={translate(STRING.ENTITY_TYPE_CAPTURE_SET)}
          />
        )}
        {item.canDelete && (
          <DeleteEntityDialog
            collection={API_ROUTES.CAPTURE_SETS}
            id={item.id}
            type={translate(STRING.ENTITY_TYPE_CAPTURE_SET)}
          />
        )}
      </Toolbar>
    ),
  },
]
