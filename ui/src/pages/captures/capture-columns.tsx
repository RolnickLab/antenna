import { Capture } from 'data-services/models/capture'
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

export const columns: (projectId: string) => TableColumn<Capture>[] = (
  projectId: string
) => [
  {
    id: 'thumbnail',
    name: translate(STRING.FIELD_LABEL_THUMBNAIL),
    renderCell: (item: Capture) => {
      const detailsRoute = item.sessionId
        ? getAppRoute({
            to: APP_ROUTES.SESSION_DETAILS({
              projectId: projectId,
              sessionId: item.sessionId,
            }),
            filters: {
              capture: item.id,
            },
          })
        : undefined

      return (
        <ImageTableCell
          images={[{ src: item.src }]}
          theme={ImageCellTheme.Light}
          to={detailsRoute}
        />
      )
    },
  },
  {
    id: 'timestamp',
    name: translate(STRING.FIELD_LABEL_TIMESTAMP),
    sortField: 'timestamp',
    renderCell: (item: Capture) => {
      const detailsRoute = item.sessionId
        ? getAppRoute({
            to: APP_ROUTES.SESSION_DETAILS({
              projectId: projectId,
              sessionId: item.sessionId,
            }),
            filters: {
              capture: item.id,
            },
          })
        : undefined

      if (detailsRoute) {
        return (
          <Link to={detailsRoute}>
            <BasicTableCell
              value={item.dateTimeLabel}
              theme={CellTheme.Primary}
            />
          </Link>
        )
      }

      return <BasicTableCell value={item.dateTimeLabel} />
    },
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    sortField: 'deployment__name',
    renderCell: (item: Capture) => {
      if (!item.deploymentId) {
        return <></>
      }

      return (
        <Link
          to={APP_ROUTES.DEPLOYMENT_DETAILS({
            projectId,
            deploymentId: item.deploymentId,
          })}
        >
          <BasicTableCell
            value={item.deploymentLabel}
            theme={CellTheme.Primary}
          />
        </Link>
      )
    },
  },
  {
    id: 'session',
    name: translate(STRING.FIELD_LABEL_SESSION),
    sortField: 'event__start',
    renderCell: (item: Capture) => {
      if (!item.sessionId) {
        return <></>
      }

      return (
        <Link
          to={APP_ROUTES.SESSION_DETAILS({
            projectId,
            sessionId: item.sessionId,
          })}
        >
          <BasicTableCell value={item.sessionLabel} theme={CellTheme.Primary} />
        </Link>
      )
    },
  },
  {
    id: 'occurrences',
    name: translate(STRING.FIELD_LABEL_OCCURRENCES),
    sortField: 'occurrences_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Capture) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { detections__source_image: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'taxa',
    name: translate(STRING.FIELD_LABEL_TAXA),
    sortField: 'taxa_count',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Capture) => <BasicTableCell value={item.numTaxa} />,
  },
]
