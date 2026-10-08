import { Project } from 'data-services/models/project'
import {
  BasicTableCell,
  CellTheme,
  DateTableCell,
  ImageCellTheme,
  ImageTableCell,
  TableColumn,
  TextAlign,
} from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

const countColumn = ({
  id,
  name,
  sortField,
  value,
}: {
  id: string
  name: string
  sortField?: string
  value: (item: Project) => number | undefined
}): TableColumn<Project> => ({
  id,
  name,
  sortField,
  styles: { textAlign: TextAlign.Right },
  renderCell: (item: Project) => <BasicTableCell value={value(item)} />,
})

export const columns: TableColumn<Project>[] = [
  {
    id: 'image',
    name: translate(STRING.FIELD_LABEL_IMAGE),
    renderCell: (item: Project) => (
      <ImageTableCell
        images={item.image ? [{ src: item.image }] : []}
        theme={ImageCellTheme.Light}
        to={APP_ROUTES.PROJECT_DETAILS({ projectId: item.id })}
      />
    ),
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Project) => (
      <Link to={APP_ROUTES.PROJECT_DETAILS({ projectId: item.id })}>
        <BasicTableCell
          value={item.name}
          details={item.isDraft ? [translate(STRING.DRAFT)] : undefined}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  countColumn({
    id: 'deployments',
    name: translate(STRING.NAV_ITEM_DEPLOYMENTS),
    sortField: 'deployments_count',
    value: (item) => item.numDeployments,
  }),
  countColumn({
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    sortField: 'captures_count',
    value: (item) => item.numCaptures,
  }),
  countColumn({
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'occurrences_count',
    value: (item) => item.numOccurrences,
  }),
  // Not sortable: each project counts its taxa with its own default filters.
  countColumn({
    id: 'taxa',
    name: translate(STRING.FIELD_LABEL_TAXA),
    value: (item) => item.numTaxa,
  }),
  countColumn({
    id: 'members',
    name: translate(STRING.FIELD_LABEL_MEMBERS),
    sortField: 'members_count',
    value: (item) => item.numMembers,
  }),
  {
    id: 'last-capture',
    name: translate(STRING.FIELD_LABEL_LAST_CAPTURE),
    sortField: 'last_capture_timestamp',
    renderCell: (item: Project) => (
      <DateTableCell date={item.lastCaptureDate} />
    ),
  },
  {
    id: 'last-occurrence-update',
    name: translate(STRING.FIELD_LABEL_LAST_OCCURRENCE_UPDATE),
    sortField: 'last_occurrence_updated_at',
    renderCell: (item: Project) => (
      <DateTableCell date={item.lastOccurrenceUpdateDate} />
    ),
  },
  {
    id: 'last-job-update',
    name: translate(STRING.FIELD_LABEL_LAST_JOB_UPDATE),
    sortField: 'last_job_updated_at',
    renderCell: (item: Project) => (
      <DateTableCell date={item.lastJobUpdateDate} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Project) => <DateTableCell date={item.createdAt} />,
  },
]
