import { TaxonInfo } from 'components/taxon/taxon-info/taxon-info'
import { Occurrence } from 'data-services/models/occurrence'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { IdentificationStatus } from 'design-system/components/identification/identification-status/identification-status'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { TABS } from 'pages/occurrence-details/occurrence-details'
import { RejectId } from 'pages/occurrence-details/reject-id/reject-id'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'
import styles from './occurrences.module.scss'

export const columns: (projectId: string) => TableColumn<Occurrence>[] = (
  projectId: string
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_SNAPSHOTS),
    styles: {
      textAlign: TextAlign.Center,
    },
    renderCell: (item: Occurrence, rowIndex: number) => {
      const isOddRow = rowIndex % 2 == 0
      const detailsRoute = getAppRoute({
        to: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId,
          occurrenceId: item.id,
        }),
        keepSearchParams: true,
      })

      return (
        <ImageTableCell
          images={item.images}
          theme={isOddRow ? ImageCellTheme.Default : ImageCellTheme.Light}
          to={detailsRoute}
        />
      )
    },
  },
  {
    id: 'id',
    name: translate(STRING.FIELD_LABEL_TAXON),
    sortField: 'determination__name',
    renderCell: (item: Occurrence) => (
      <TaxonCell item={item} projectId={projectId} />
    ),
  },
  {
    id: 'score',
    name: translate(STRING.FIELD_LABEL_SCORE),
    sortField: 'determination_score',
    renderCell: (item: Occurrence) => (
      <ScoreCell item={item} projectId={projectId} />
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    sortField: 'deployment',
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
    sortField: 'event',
    renderCell: (item: Occurrence) => (
      <Link
        to={APP_ROUTES.SESSION_DETAILS({
          projectId,
          sessionId: item.sessionId,
        })}
      >
        <BasicTableCell value={item.sessionLabel} theme={CellTheme.Primary} />
      </Link>
    ),
  },
  {
    id: 'date',
    name: translate(STRING.FIELD_LABEL_DATE_OBSERVED),
    sortField: 'first_appearance_timestamp',
    renderCell: (item: Occurrence) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SESSION_DETAILS({
            projectId,
            sessionId: item.sessionId,
          }),
          filters: {
            occurrence: item.id,
            timestamp: item.firstAppearanceTimestamp,
          },
        })}
      >
        <BasicTableCell value={item.dateLabel} />
      </Link>
    ),
  },
  {
    id: 'time',
    sortField: 'first_appearance_time',
    name: translate(STRING.FIELD_LABEL_TIME_OBSERVED),
    renderCell: (item: Occurrence) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.SESSION_DETAILS({
            projectId,
            sessionId: item.sessionId,
          }),
          filters: {
            occurrence: item.id,
            timestamp: item.firstAppearanceTimestamp,
          },
        })}
      >
        <BasicTableCell value={item.timeLabel} />
      </Link>
    ),
  },
  {
    id: 'duration',
    name: translate(STRING.FIELD_LABEL_DURATION),
    sortField: 'duration',
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.durationLabel} />
    ),
  },
  {
    id: 'detections',
    name: translate(STRING.FIELD_LABEL_DETECTIONS),
    sortField: 'detections_count',
    renderCell: (item: Occurrence) => (
      <BasicTableCell value={item.numDetections} />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Occurrence) => <BasicTableCell value={item.createdAt} />,
  },
]

const TaxonCell = ({
  item,
  projectId,
}: {
  item: Occurrence
  projectId: string
}) => {
  const { userInfo } = useUserInfo()
  const navigate = useNavigate()
  const detailsRoute = getAppRoute({
    to: APP_ROUTES.OCCURRENCE_DETAILS({
      projectId,
      occurrenceId: item.id,
    }),
    keepSearchParams: true,
  })
  const canUpdate = item.userPermissions.includes(UserPermission.Update)
  const agreed = userInfo?.id
    ? userInfo.id === item.determinationVerifiedBy?.id
    : false

  return (
    <div className={styles.taxonCell}>
      <BasicTableCell>
        <div className={styles.taxonCellContent}>
          <Link to={detailsRoute}>
            <TaxonInfo taxon={item.determinationTaxon} />
          </Link>
          {canUpdate && (
            <div className={styles.taxonActions}>
              <Agree
                agreed={agreed}
                agreeWith={{
                  identificationId: item.determinationIdentificationId,
                  predictionId: item.determinationPredictionId,
                }}
                buttonTheme={ButtonTheme.Success}
                occurrenceId={item.id}
                taxonId={item.determinationTaxon.id}
              />
              <Button
                label={translate(STRING.SUGGEST_ID_SHORT)}
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
              <RejectId
                occurrenceId={item.id}
                occurrenceTaxonId={item.determinationTaxon.id}
              />
            </div>
          )}
        </div>
      </BasicTableCell>
    </div>
  )
}

const ScoreCell = ({
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
    <div className={styles.scoreCell}>
      <BasicTableCell>
        <div className={styles.scoreCellContent}>
          <Tooltip
            content={
              item.determinationVerified
                ? translate(STRING.VERIFIED_BY, {
                    name: item.determinationVerifiedBy?.name,
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
          <span className={styles.scoreCellLabel}>
            {item.determinationScoreLabel}
          </span>
        </div>
      </BasicTableCell>
    </div>
  )
}
