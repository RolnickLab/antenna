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
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Species>[] = [
  {
    id: 'snapshots',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
    styles: {
      padding: '16px 32px',
    },
    renderCell: (item: Species, rowIndex: number) => {
      const isOddRow = rowIndex % 2 == 0

      return (
        <ImageTableCell
          images={item.images}
          theme={isOddRow ? ImageCellTheme.Default : ImageCellTheme.Light}
        />
      )
    },
  },
  {
    id: 'name',
    name: 'Name',
    renderCell: (item: Species) => (
      <Link to={`/species/species-id`}>
        <BasicTableCell
          value={item.name}
          details={['WIP']}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'detections',
    name: translate(STRING.TABLE_COLUMN_DETECTIONS),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.TABLE_COLUMN_OCCURRENCES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <BasicTableCell value={item.numOccurrences} />
    ),
  },
  {
    id: 'training-images',
    name: 'Training Images',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <Link to={`https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${item.name}`} target='_blank'>
        <BasicTableCell
          value={'GBIF'}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
]
