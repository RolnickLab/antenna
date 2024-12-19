import { Pipeline } from 'data-services/models/pipeline'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn } from 'design-system/components/table/types'
import { PipelineDetailsDialog } from 'pages/pipeline-details/pipeline-details-dialog'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Pipeline>[] = () => [
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
      <BasicTableCell>
        <PipelineDetailsDialog id={item.id} name={item.name} />
      </BasicTableCell>
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
  {
    id: 'backends-online',
    name: 'Backends Online',
    sortField: 'backends_online',
    renderCell: (item: Pipeline) => (
      <BasicTableCell value={item.backendsOnline} />
    ),
  },
  {
    id: 'backends-online-last-checked',
    name: 'Backends Online Last Checked',
    sortField: 'backends_online_last_checked',
    renderCell: (item: Pipeline) => (
      <BasicTableCell value={item.backendsOnlineLastChecked} />
    ),
  },
]
