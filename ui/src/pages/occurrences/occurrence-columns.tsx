import { OODScore } from 'components/ood-score'
import { Occurrence } from 'data-services/models/occurrence'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { SearchIcon } from 'lucide-react'
import { Button, IdentificationScore, TaxonDetails } from 'nova-ui-kit'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { FeatureControl } from 'pages/occurrence-details/feature-control/feature-control'
import { TABS } from 'pages/occurrence-details/occurrence-details'
import { IdQuickActions } from 'pages/occurrence-details/reject-id/id-quick-actions'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'
import styles from './occurrences.module.scss'

export const columns: (
  projectId: string,
  showQuickActions?: boolean
) => TableColumn<Occurrence>[] = (
  projectId: string,
  showQuickActions?: boolean
) => [
  {
    id: 'snapshots',
    name: translate(STRING.FIELD_LABEL_SNAPSHOTS),
    styles: {
      textAlign: TextAlign.Center,
    },
    renderCell: (item: Occurrence) => {
      const detailsRoute = getAppRoute({
        to: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId,
          occurrenceId: item.id,
        }),
        keepSearchParams: true,
      })

      return (
        <div className="relative group">
          <ImageTableCell
            images={[item.images[0]]}
            theme={ImageCellTheme.Light}
            to={detailsRoute}
          />
          <div className="absolute bottom-4 right-5 hidden group-hover:block">
            <FeatureControl occurrence={item} />
          </div>
        </div>
      )
    },
  },
  {
    id: 'id',
    name: translate(STRING.FIELD_LABEL_TAXON),
    sortField: 'determination__name',
    renderCell: (item: Occurrence) => (
      <TaxonCell
        id={item.id}
        item={item}
        projectId={projectId}
        showQuickActions={showQuickActions}
      />
    ),
  },
  {
    id: 'score',
    name: translate(STRING.FIELD_LABEL_SCORE),
    sortField: 'determination_score',
    renderCell: (item: Occurrence) => <ScoreCell item={item} />,
  },
  {
    id: 'ood-score',
    name: translate(STRING.FIELD_LABEL_OOD_SCORE),
    sortField: 'determination_ood_score',
    renderCell: (item: Occurrence) => (
      <BasicTableCell>
        <OODScore occurrence={item} />
      </BasicTableCell>
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
    renderCell: (item: Occurrence) => {
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
    id: 'date',
    name: translate(STRING.FIELD_LABEL_DATE_OBSERVED),
    sortField: 'first_appearance_timestamp',
    renderCell: (item: Occurrence) => <BasicTableCell value={item.dateLabel} />,
  },
  {
    id: 'time',
    sortField: 'first_appearance_time',
    name: translate(STRING.FIELD_LABEL_TIME_OBSERVED),
    renderCell: (item: Occurrence) => <BasicTableCell value={item.timeLabel} />,
  },
  {
    id: 'duration',
    name: translate(STRING.FIELD_LABEL_DURATION),
    sortField: 'duration',
    renderCell: (item: Occurrence) => (
      <BasicTableCell
        value={item.durationLabel ?? translate(STRING.VALUE_NOT_AVAILABLE)}
      />
    ),
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Occurrence) => <BasicTableCell value={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Occurrence) => <BasicTableCell value={item.updatedAt} />,
  },
]

const TaxonCell = ({
  id,
  item,
  projectId,
  showQuickActions,
}: {
  id?: string
  item: Occurrence
  projectId: string
  showQuickActions?: boolean
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
  const agreed = userInfo ? item.userAgreed(userInfo.id) : false

  return (
    <div id={id} className={styles.taxonCell}>
      <BasicTableCell>
        <div className={styles.taxonCellContent}>
          <Link to={detailsRoute}>
            <TaxonDetails compact taxon={item.determinationTaxon} />
          </Link>
          {showQuickActions && canUpdate && (
            <div className={styles.taxonActions}>
              <Agree
                agreed={agreed}
                agreeWith={{
                  identificationId: item.determinationIdentificationId,
                  predictionId: item.determinationPredictionId,
                }}
                applied
                occurrenceId={item.id}
                taxonId={item.determinationTaxon.id}
              />
              <BasicTooltip asChild content={translate(STRING.SUGGEST_ID)}>
                <Button
                  onClick={() =>
                    navigate(detailsRoute, {
                      state: {
                        defaultTab: TABS.IDENTIFICATION,
                        suggestIdOpen: true,
                      },
                    })
                  }
                  size="icon"
                  variant="outline"
                >
                  <SearchIcon className="w-4 h-4" />
                </Button>
              </BasicTooltip>
              <IdQuickActions
                occurrenceIds={[item.id]}
                occurrenceTaxons={[item.determinationTaxon]}
                zIndex={1}
              />
            </div>
          )}
        </div>
      </BasicTableCell>
    </div>
  )
}

const ScoreCell = ({ item }: { item: Occurrence }) => (
  <div className={styles.scoreCell}>
    <BasicTableCell>
      <BasicTooltip
        content={
          item.determinationVerified
            ? translate(STRING.VERIFIED_BY, {
                name: item.determinationVerifiedBy?.name,
              })
            : translate(STRING.MACHINE_PREDICTION_SCORE, {
                score: `${item.determinationScore}`,
              })
        }
      >
        <div className={styles.scoreCellContent}>
          <IdentificationScore
            confirmed={item.determinationVerified}
            confidenceScore={item.determinationScore}
          />
          <span className={styles.scoreCellLabel}>
            {item.determinationScoreLabel}
          </span>
        </div>
      </BasicTooltip>
    </BasicTableCell>
  </div>
)
