import { Pipeline } from 'data-services/models/pipeline'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { CellTheme, TableColumn } from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { DefaultPipelineBadge } from './default-pipeline-badge'

export const columns: (
  projectId: string,
  defaultProcessingPipelineId?: string
) => TableColumn<Pipeline>[] = (
  projectId: string,
  defaultProcessingPipelineId?: string
) => [
  {
    id: 'id',
    sortField: 'id',
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: Pipeline) => <BasicTableCell value={item.id} />,
  },
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: Pipeline) => (
      <Link
        to={APP_ROUTES.PIPELINE_DETAILS({ projectId, pipelineId: item.id })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'default',
    name: '',
    renderCell: (item: Pipeline) =>
      item.id === defaultProcessingPipelineId ? (
        <BasicTableCell>
          <DefaultPipelineBadge projectId={projectId} />
        </BasicTableCell>
      ) : (
        <></>
      ),
  },
  {
    id: 'processing-services-online',
    name: 'Processing services online',
    sortField: 'processing_services_online',
    renderCell: (item: Pipeline) => (
      <BasicTableCell value={item.processingServicesOnline} />
    ),
  },
  {
    id: 'processing-services-online-last-seen',
    name: 'Status last seen',
    sortField: 'processing_services_online_last_seen',
    renderCell: (item: Pipeline) => (
      <BasicTableCell value={item.processingServicesOnlineLastSeen} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Pipeline) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Pipeline) => <BasicTableCell value={item.updatedAt} />,
  },
]
