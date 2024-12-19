import { Pipeline } from 'data-services/models/pipeline'
import { Backend } from 'data-services/models/backend'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  Table,
  TableBackgroundTheme,
} from 'design-system/components/table/table/table'
import { TableColumn } from 'design-system/components/table/types'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Pipeline>[] = [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Pipeline) => (
      <BasicTableCell
        value={item.name}
        style={{ width: '240px', whiteSpace: 'normal' }}
      />
    ),
  },
  {
    id: 'description',
    name: translate(STRING.FIELD_LABEL_DESCRIPTION),
    renderCell: (item: Pipeline) => (
      <BasicTableCell
        value={item.description}
        style={{ width: '240px', whiteSpace: 'normal' }}
      />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    renderCell: (item: Pipeline) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    renderCell: (item: Pipeline) => <BasicTableCell value={item.updatedAt} />,
  },
]

export const BackendPipelines = ({ backend }: { backend: Backend }) => (
  <Table
    backgroundTheme={TableBackgroundTheme.White}
    items={backend.pipelines}
    columns={columns}
  />
)
