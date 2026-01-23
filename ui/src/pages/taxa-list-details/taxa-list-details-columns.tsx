import { Species } from 'data-services/models/species'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { TaxonDetails } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { RemoveTaxaListTaxonDialog } from './remove-taxa-list-taxon/remove-taxa-list-taxon-dialog'

export const columns: (params: {
  canUpdate?: boolean
  projectId: string
  taxaListId: string
}) => TableColumn<Species>[] = ({ canUpdate, projectId, taxaListId }) => [
  {
    id: 'cover-image',
    name: translate(STRING.FIELD_LABEL_IMAGE),
    sortField: 'cover_image_url',
    renderCell: (item: Species) => {
      return (
        <ImageTableCell
          images={item.coverImage ? [{ src: item.coverImage.url }] : []}
          theme={ImageCellTheme.Light}
          to={getAppRoute({
            to: APP_ROUTES.TAXA_LIST_TAXON_DETAILS({
              projectId,
              taxaListId,
              taxonId: item.id,
            }),
            keepSearchParams: true,
          })}
        />
      )
    },
  },
  {
    id: 'name',
    sortField: 'name',
    name: translate(STRING.FIELD_LABEL_TAXON),
    renderCell: (item: Species) => (
      <BasicTableCell>
        <Link
          to={getAppRoute({
            to: APP_ROUTES.TAXA_LIST_TAXON_DETAILS({
              projectId,
              taxaListId,
              taxonId: item.id,
            }),
            keepSearchParams: true,
          })}
        >
          <TaxonDetails compact taxon={item} />
        </Link>
      </BasicTableCell>
    ),
  },
  {
    id: 'rank',
    name: 'Taxon rank',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => <BasicTableCell value={item.rank} />,
  },
  {
    id: 'actions',
    name: '',
    styles: {
      padding: '16px',
      width: '100%',
    },
    renderCell: (item: Species) => (
      <div className="flex items-center justify-end gap-2 p-4">
        {canUpdate ? (
          <RemoveTaxaListTaxonDialog
            taxaListId={taxaListId}
            taxonId={item.id}
          />
        ) : null}
      </div>
    ),
  },
]
