import { Occurrence } from 'data-services/models/occurrence'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const columns: TableColumn<Occurrence>[] = [
  {
    id: 'snapshots',
    name: translate(STRING.TABLE_COLUMN_MOST_RECENT),
    styles: {
      padding: '16px 32px 16px 50px',
    },
    renderCell: (item: Occurrence, rowIndex: number) => {
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
    id: 'id',
    sortField: 'id',
    name: translate(STRING.TABLE_COLUMN_ID),
    renderCell: (item: Occurrence) => (
      <Link to={`/occurrences/${item.id}`}>
        <BasicTableCell
          value={item.categoryLabel}
          details={['WIP', `${translate(STRING.SCORE)}: ${item.categoryScore}`]}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
    renderCell: (item: Occurrence) => (
      <Link to={`/deployments/${item.deploymentId}`}>
        <BasicTableCell
          value={item.deploymentLabel}
          details={['WIP']}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'session',
    name: translate(STRING.TABLE_COLUMN_SESSION),
    renderCell: (item: Occurrence) => (
      <Link to={`/sessions/${item.sessionId}`}>
        <BasicTableCell
          value={item.sessionLabel}
          details={[item.sessionTimespan]}
          theme={CellTheme.Primary}
        />
      </Link>
    ),
  },
  {
    id: 'appearance',
    name: translate(STRING.TABLE_COLUMN_APPEARANCE),
    renderCell: () => (
      <BasicTableCell
        value={'WIP'}
        details={['WIP']}
        theme={CellTheme.Primary}
      />
    ),
  },
]
