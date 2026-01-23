import { API_ROUTES } from 'data-services/constants'
import { TaxaList } from 'data-services/models/taxa-list'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { DeleteEntityDialog } from 'pages/project/entities/delete-entity-dialog'
import { UpdateEntityDialog } from 'pages/project/entities/entity-details-dialog'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { AddTaxaListTaxonPopover } from '../taxa-list-details/add-taxa-list-taxon/add-taxa-list-taxon-popover'

export const columns: (projectId: string) => TableColumn<TaxaList>[] = (
  projectId: string
) => [
  {
    id: 'name',
    name: translate(STRING.FIELD_LABEL_NAME),
    sortField: 'name',
    renderCell: (item: TaxaList) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.TAXA_LIST_DETAILS({
            projectId,
            taxaListId: item.id,
          }),
        })}
      >
        <BasicTableCell value={item.name} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'description',
    name: translate(STRING.FIELD_LABEL_DESCRIPTION),
    sortField: 'description',
    renderCell: (item: TaxaList) => <BasicTableCell value={item.description} />,
  },
  {
    id: 'taxa',
    name: translate(STRING.FIELD_LABEL_TAXA),
    sortField: 'annotated_taxa_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: TaxaList) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.TAXA({
            projectId,
          }),
          filters: { include_unobserved: 'true', taxa_list_id: item.id },
        })}
      >
        <BasicTableCell value={item.taxaCount} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: TaxaList) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: TaxaList) => <BasicTableCell value={item.updatedAt} />,
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: TaxaList) => (
      <div className="flex items-center justify-end gap-2 p-4">
        {item.canUpdate ? (
          <AddTaxaListTaxonPopover taxaListId={item.id} />
        ) : null}
        {item.canUpdate ? (
          <UpdateEntityDialog
            collection={API_ROUTES.TAXA_LISTS}
            entity={item}
            isCompact
            type={translate(STRING.ENTITY_TYPE_TAXA_LIST)}
          />
        ) : null}
        {item.canDelete ? (
          <DeleteEntityDialog
            collection={API_ROUTES.TAXA_LISTS}
            id={item.id}
            type={translate(STRING.ENTITY_TYPE_TAXA_LIST)}
          />
        ) : null}
      </div>
    ),
  },
]
