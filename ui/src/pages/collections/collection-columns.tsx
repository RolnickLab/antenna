import { Collection } from 'data-services/models/collection'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { TableColumn, TextAlign } from 'design-system/components/table/types'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Collection>[] = () => [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    renderCell: (item: Collection) => <BasicTableCell value={item.name} />,
  },
  {
    id: 'sampling-method',
    name: 'Sampling method',
    renderCell: (item: Collection) => (
      <BasicTableCell value={item.method} details={item.methodDetails} />
    ),
  },
  {
    id: 'captures',
    name: translate(STRING.FIELD_LABEL_CAPTURES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Collection) => <BasicTableCell value={item.numImages} />,
  },
  {
    id: 'created-at',
    name: 'Created at',
    sortField: 'created_at',
    renderCell: (item: Collection) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: 'Updated at',
    sortField: 'updated_at',
    renderCell: (item: Collection) => <BasicTableCell value={item.updatedAt} />,
  },
]
