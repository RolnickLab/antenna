import { Tag } from 'components/taxon-tags/tag'
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

export const columns: (project: {
  projectId: string
  featureFlags?: { [key: string]: boolean }
}) => TableColumn<Species>[] = ({ projectId, featureFlags }) => [
  {
    id: 'cover-image',
    name: 'Cover image',
    sortField: 'cover_image_url',
    renderCell: (item: Species) => {
      return (
        <ImageTableCell
          images={item.coverImage ? [{ src: item.coverImage.url }] : []}
          theme={ImageCellTheme.Light}
          to={APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id })}
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
        <div className="grid gap-4">
          <Link
            to={getAppRoute({
              to: APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id }),
              keepSearchParams: true,
            })}
          >
            <TaxonDetails compact taxon={item} />
          </Link>
          {featureFlags?.tags && item.tags.length ? (
            <div className="flex flex-wrap gap-1">
              {item.tags.map((tag) => (
                <Tag key={tag.id} name={tag.name} />
              ))}
            </div>
          ) : null}
        </div>
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
]
