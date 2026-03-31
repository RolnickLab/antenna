import { DeterminationScore } from 'components/determination-score'
import { Occurrence } from 'data-services/models/occurrence'
import { BasicTableCell } from 'design-system/components/table/basic-table-cell/basic-table-cell'
import { DateTableCell } from 'design-system/components/table/date-table-cell/date-table-cell'
import { ImageTableCell } from 'design-system/components/table/image-table-cell/image-table-cell'
import {
  CellTheme,
  ImageCellTheme,
  TableColumn,
  TextAlign,
} from 'design-system/components/table/types'
import { TaxonDetails } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { OccurrenceActions } from './occurrence-actions'
import styles from './occurrences.module.scss'

export const columns: (
  projectId: string,
  showQuickActions?: boolean
) => TableColumn<Occurrence>[] = (projectId: string, showActions?: boolean) => [
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
        <ImageTableCell
          images={[item.images[0]]}
          theme={ImageCellTheme.Light}
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
      <TaxonCell
        id={item.id}
        item={item}
        projectId={projectId}
        showActions={showActions}
      />
    ),
  },
  {
    id: 'score',
    name: translate(STRING.FIELD_LABEL_SCORE),
    tooltip: translate(STRING.TOOLTIP_SCORE),
    sortField: 'determination_score',
    renderCell: (item: Occurrence) => (
      <BasicTableCell>
        <DeterminationScore
          score={item.determinationScore}
          scoreLabel={item.determinationScoreLabel}
          tooltip={
            item.determinationVerified
              ? translate(STRING.VERIFIED_BY, {
                  name: item.determinationVerifiedBy?.name,
                })
              : translate(STRING.MACHINE_PREDICTION_SCORE, {
                  score: `${item.determinationScore}`,
                })
          }
          verified={item.determinationVerified}
        />
      </BasicTableCell>
    ),
  },
  {
    id: 'deployment',
    name: translate(STRING.FIELD_LABEL_DEPLOYMENT),
    tooltip: translate(STRING.TOOLTIP_DEPLOYMENT),
    sortField: 'deployment',
    renderCell: (item: Occurrence) => {
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
    tooltip: translate(STRING.TOOLTIP_SESSION),
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
    renderCell: (item: Occurrence) => <DateTableCell date={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Occurrence) => <DateTableCell date={item.updatedAt} />,
  },
]

const TaxonCell = ({
  id,
  item,
  projectId,
  showActions,
}: {
  id?: string
  item: Occurrence
  projectId: string
  showActions?: boolean
}) => {
  const detailsRoute = getAppRoute({
    to: APP_ROUTES.OCCURRENCE_DETAILS({
      projectId,
      occurrenceId: item.id,
    }),
    keepSearchParams: true,
  })

  return (
    <div id={id} className={styles.taxonCell}>
      <BasicTableCell style={{ minWidth: '320px' }}>
        <div className={styles.taxonCellContent}>
          <Link to={detailsRoute}>
            <TaxonDetails compact taxon={item.determinationTaxon} />
          </Link>
          <OccurrenceActions item={item} showActions={showActions} />
        </div>
      </BasicTableCell>
    </div>
  )
}
