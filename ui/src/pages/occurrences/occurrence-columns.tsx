import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { Occurrence } from 'data-services/models/occurrence'
import { Button } from 'design-system/components/button/button'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { TABS } from 'pages/occurrence-details/occurrence-details'
import { Link, useNavigate } from 'react-router-dom'
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
  const navigate = useNavigate()
  const detailsRoute = getAppRoute({
    to: APP_ROUTES.OCCURRENCE_DETAILS({
      projectId,
      occurrenceId: item.id,
    }),
    keepSearchParams: true,
  })

  return (
    <div className={styles.taxonCell}>
      <BasicTableCell>
        <div className={styles.taxon}>
          <Link to={detailsRoute}>
            <TaxonInfo taxon={item.determinationTaxon} />
          </Link>
        </div>
        <div className={styles.taxonActions}>
          <IdentificationStatus
            isVerified={item.determinationVerified}
            score={item.determinationScore}
          />
          <Button
            label="Suggest ID"
            onClick={() =>
              navigate(detailsRoute, {
                state: {
                  defaultTab: TABS.IDENTIFICATION,
                  suggestIdOpen: true,
                },
              })
            }
          />
        </div>
      </BasicTableCell>
    </div>
  )
}
