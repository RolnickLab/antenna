import { Capture } from 'data-services/models/capture'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (projectId: string) => TableColumn<Capture>[] = (
  projectId: string
) => [
  {
    id: 'thumbnail',
    name: 'Thumbnail',
    renderCell: (item: Capture, rowIndex: number) => {
      const isOddRow = rowIndex % 2 == 0

      return (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.SESSION_DETAILS({
              projectId: projectId,
              sessionId: item.sessionId,
            }),
            filters: {
              capture: item.id,
            },
          })}
        >
          <ImageTableCell
            images={[{ src: item.src }]}
            theme={isOddRow ? ImageCellTheme.Default : ImageCellTheme.Light}
          />
        </Link>
      )
    },
  },
  {
    id: 'timestamp',
    name: 'Timestamp',
    sortField: 'timestamp',
    renderCell: (item: Capture) => (
      <BasicTableCell value={item.dateTimeLabel} />
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    renderCell: () => <BasicTableCell />,
  },
  {
    id: 'session',
    name: translate(STRING.FIELD_LABEL_SESSION),
    renderCell: () => <BasicTableCell />,
  },
  {
    id: 'detections',
    name: translate(STRING.FIELD_LABEL_DETECTIONS),
    sortField: 'detections_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Capture) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    renderCell: () => <BasicTableCell />,
  },
]
