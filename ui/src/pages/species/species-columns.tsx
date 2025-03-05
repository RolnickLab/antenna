import { Species } from 'data-services/models/species'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import {
  CellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { TaxonDetails } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Species>[] = (
  projectId: string
) => [
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
          <TaxonDetails compact taxon={item} />
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
        <BasicTableCell
          value={item.numOccurrences || 'View all'}
          theme={CellTheme.Bubble}
        />
      </Link>
    ),
  },
  {
    id: 'score',
    sortField: 'best_determination_score',
    name: translate(STRING.FIELD_LABEL_BEST_SCORE),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <BasicTableCell value={item.scoreLabel} style={{ textAlign: 'right' }} />
    ),
  },
  {
    id: 'rank',
    sortField: 'rank',
    name: 'Taxon rank',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => <BasicTableCell value={item.rank} />,
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
