import { Occurrence } from 'data-services/models/occurrence'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { TaxonInfo } from 'design-system/components/taxon/taxon-info/taxon-info'
import { SuggestId } from 'pages/occurrence-details/suggest-id/suggest-id'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './occurrences.module.scss'

export const columns: (projectId: string) => TableColumn<Occurrence>[] = (
  projectId: string
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_MOST_RECENT),
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
    name: translate(STRING.FIELD_LABEL_ID),
    renderCell: (item: Occurrence) => (
      <TaxonCell item={item} projectId={projectId} />
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    renderCell: (item: Occurrence) => (
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
    ),
  },
  {
    id: 'session',
    name: translate(STRING.FIELD_LABEL_SESSION),
    renderCell: (item: Occurrence) => (
      <Link to={APP_ROUTES.SESSION_DETAILS({ projectId, sessionId: item.id })}>
        <BasicTableCell value={item.sessionLabel} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'date',
    name: translate(STRING.FIELD_LABEL_DATE),
    renderCell: (item: Occurrence) => <BasicTableCell value={item.dateLabel} />,
  },
  {
    id: 'time',
    name: translate(STRING.FIELD_LABEL_TIME),
    renderCell: (item: Occurrence) => <BasicTableCell value={item.timeLabel} />,
  },
  {
    id: 'duration',
    name: translate(STRING.FIELD_LABEL_DURATION),
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'detections',
    name: translate(STRING.FIELD_LABEL_DETECTIONS),
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
]

const TaxonCell = ({
  item,
  projectId,
}: {
  item: Occurrence
  projectId: string
}) => {
  return (
    <div className={styles.taxonCell}>
      <BasicTableCell>
        <Link
          to={getAppRoute({
            to: APP_ROUTES.OCCURRENCE_DETAILS({
              projectId,
              occurrenceId: item.id,
            }),
            keepSearchParams: true,
          })}
        >
          <TaxonInfo taxon={item.determinationTaxon} />
        </Link>
        <div className={styles.taxonActions}>
          {item.determinationScore !== undefined ? (
            <IdentificationStatus score={item.determinationScore} />
          ) : null}
          <SuggestId />
        </div>
      </BasicTableCell>
    </div>
  )
}
