import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { Occurrence } from 'data-services/models/occurrence'
import { ButtonTheme } from 'design-system/components/button/button'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
} from 'design-system/components/table/types'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { TABS } from 'pages/occurrence-details/occurrence-details'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import styles from './occurrences.module.scss'

export const columns: (projectId: string) => TableColumn<Occurrence>[] = (
  projectId: string
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_MOST_RECENT),
    sortField: 'updated_at',
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
  const canUpdate = item.userPermissions.includes(UserPermission.Update)
  const showQuickActions = !item.determinationVerified && canUpdate

  return (
    <div className={styles.taxonCell}>
      <BasicTableCell>
        <div className={styles.taxonCellContent}>
          <Tooltip
            content={
              item.determinationVerified
                ? translate(STRING.VERIFIED_BY, {
                    name: item.determinationVerifiedBy as string,
                  })
                : translate(STRING.MACHINE_PREDICTION_SCORE, {
                    score: item.determinationScore,
                  })
            }
          >
            <IdentificationStatus
              isVerified={item.determinationVerified}
              score={item.determinationScore}
              onStatusClick={() =>
                navigate(detailsRoute, {
                  state: {
                    defaultTab: TABS.IDENTIFICATION,
                  },
                })
              }
            />
          </Tooltip>
          <Link to={detailsRoute}>
            <TaxonInfo taxon={item.determinationTaxon} />
          </Link>
          {showQuickActions && (
            <div className={styles.taxonActions}>
              <Agree
                agreeWith={{
                  identificationId: item.determinationIdentificationId,
                  predictionId: item.determinationPredictionId,
                }}
                buttonTheme={ButtonTheme.Success}
                occurrenceId={item.id}
                taxonId={item.determinationTaxon.id}
              />
              <Tooltip content={translate(STRING.SUGGEST_ID)}>
                <IconButton
                  icon={IconType.ShieldAlert}
                  onClick={() =>
                    navigate(detailsRoute, {
                      state: {
                        defaultTab: TABS.IDENTIFICATION,
                        suggestIdOpen: true,
                      },
                    })
                  }
                />
              </Tooltip>
            </div>
          )}
        </div>
      </BasicTableCell>
    </div>
  )
}
