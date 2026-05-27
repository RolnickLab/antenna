import { TaxonDetails } from 'components/taxon-details/taxon-details'
import { Species } from 'data-services/models/species'
import {
  BasicTableCell,
  ImageCellTheme,
  ImageTableCell,
  TableColumn,
  TextAlign,
  Toolbar,
} from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { RemoveTaxaListTaxonDialog } from './remove-taxa-list-taxon/remove-taxa-list-taxon-dialog'

export const columns = ({
  canUpdate,
  projectId,
  taxaListId,
}: {
  canUpdate?: boolean
  projectId: string
  taxaListId: string
}): TableColumn<Species>[] => [
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
    sticky: true,
    renderCell: (item: Species) => (
      <Toolbar>
        {canUpdate ? (
          <RemoveTaxaListTaxonDialog
            taxaListId={taxaListId}
            taxonId={item.id}
          />
        ) : null}
      </Toolbar>
    ),
  },
]
