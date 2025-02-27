import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { Species } from 'data-services/models/species'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Species>[] = (
  projectId: string
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_SNAPSHOTS),
    styles: {
      textAlign: TextAlign.Center,
    },
    renderCell: (item: Species) => {
      const detailsRoute = getAppRoute({
        to: APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id }),
        keepSearchParams: true,
      })

      return (
        <ImageTableCell
          images={item.images}
          total={item.images.length}
          theme={ImageCellTheme.Light}
          to={detailsRoute}
        />
      )
    },
  },
  {
    id: 'name',
    sortField: 'name',
    name: translate(STRING.FIELD_LABEL_TAXON),
    renderCell: (item: Species) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id }),
          keepSearchParams: true,
        })}
      >
        <BasicTableCell>
          <TaxonInfo compact taxon={item} />
        </BasicTableCell>
      </Link>
    ),
  },
  {
    id: 'occurrences',
    sortField: 'occurrences_count',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { taxon: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'training-images',
    name: translate(STRING.FIELD_LABEL_TRAINING_IMAGES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <Link to={item.trainingImagesUrl} target="_blank">
        <BasicTableCell
          value={item.trainingImagesLabel}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
]
