import { Algorithm } from 'data-services/models/algorithm'
import { Pipeline } from 'data-services/models/pipeline'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  Table,
  TableBackgroundTheme,
} from 'design-system/components/table/table/table'
import { TableColumn } from 'design-system/components/table/types'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Algorithm>[] = [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Algorithm) => (
      <BasicTableCell
        value={item.name}
        style={{ width: '240px', whiteSpace: 'normal' }}
      />
    ),
  },
  {
    id: 'description',
    name: translate(STRING.FIELD_LABEL_DESCRIPTION),
    renderCell: (item: Algorithm) => (
      <BasicTableCell
        value={item.description}
        style={{ width: '240px', whiteSpace: 'normal' }}
      />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    renderCell: (item: Algorithm) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    renderCell: (item: Algorithm) => <BasicTableCell value={item.updatedAt} />,
  },
  {
    id: 'key',
    name: translate(STRING.FIELD_LABEL_SLUG),
    renderCell: (item: Algorithm) => <BasicTableCell value={item.key} />,
  },
]

export const PipelineAlgorithms = ({ pipeline }: { pipeline: Pipeline }) => (
  <Table
    backgroundTheme={TableBackgroundTheme.White}
    items={pipeline.algorithms}
    columns={columns}
  />
)
