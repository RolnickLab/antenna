import { DeterminationScore } from 'components/determination-score'
import { TaxonDetails } from 'components/taxon-details/taxon-details'
import { Tag } from 'components/taxon-tags/tag'
import { Species } from 'data-services/models/species'
import { ShieldCheckIcon } from 'lucide-react'
import {
  BasicTableCell,
  CellTheme,
  DateTableCell,
  ImageCellTheme,
  ImageTableCell,
  TableColumn,
  TextAlign,
} from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

export const columns: (project: {
  projectId: string
  featureFlags?: { [key: string]: boolean }
}) => TableColumn<Species>[] = ({ projectId, featureFlags }) => [
  {
    id: 'cover-image',
    name: translate(STRING.FIELD_LABEL_IMAGE),
    sortField: 'cover_image_url',
    renderCell: (item: Species) => {
      return (
        <ImageTableCell
          images={item.coverImage ? [{ src: item.coverImage.url }] : []}
          theme={ImageCellTheme.Light}
          to={getAppRoute({
            to: APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id }),
            keepSearchParams: true,
          })}
        />
      )
    },
  },
  {
    id: 'name',
    sortField: 'name',
    name: translate(STRING.FIELD_LABEL_TAXON),
    renderCell: (item: Species) => (
      <BasicTableCell>
        <div className="grid gap-4">
          <Link
            to={getAppRoute({
              to: APP_ROUTES.TAXON_DETAILS({ projectId, taxonId: item.id }),
              keepSearchParams: true,
            })}
          >
            <TaxonDetails compact taxon={item} />
          </Link>
          {featureFlags?.tags && item.tags.length ? (
            <div className="flex flex-wrap gap-1">
              {item.tags.map((tag) => (
                <Tag key={tag.id} name={tag.name} />
              ))}
            </div>
          ) : null}
        </div>
      </BasicTableCell>
    ),
  },
  {
    id: 'rank',
    name: 'Taxon rank',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => <BasicTableCell value={item.rank} />,
  },
  {
    id: 'last-seen',
    sortField: 'last_detected',
    name: 'Last seen',
    renderCell: (item: Species) =>
      item.lastDetectedOccurrenceId ? (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.TAXA({ projectId }),
            filters: {
              verifyOccurrence: String(item.lastDetectedOccurrenceId),
            },
            keepSearchParams: true,
          })}
        >
          <DateTableCell date={item.lastSeen} />
        </Link>
      ) : (
        <DateTableCell date={item.lastSeen} />
      ),
  },
  {
    id: 'occurrences',
    sortField: 'occurrences_count',
    name: translate(STRING.FIELD_LABEL_DIRECT_OCCURRENCES),
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { taxon: item.id },
        })}
      >
        <BasicTableCell value={item.numOccurrences} theme={CellTheme.Bubble} />
      </Link>
    ),
  },
  {
    id: 'verified',
    sortField: 'verified_count',
    name: 'Verified',
    styles: {
      textAlign: TextAlign.Right,
    },
    renderCell: (item: Species) => (
      <Link
        to={getAppRoute({
          to: APP_ROUTES.OCCURRENCES({ projectId }),
          filters: { taxon: item.id, verified: 'true' },
        })}
      >
        <div className="flex items-center justify-end gap-1.5">
          {item.numVerified > 0 ? (
            <ShieldCheckIcon
              aria-label={translate(STRING.VERIFIED)}
              className="w-4 h-4 text-success"
            />
          ) : null}
          <BasicTableCell value={item.numVerified} theme={CellTheme.Bubble} />
        </div>
      </Link>
    ),
  },
  {
    id: 'example',
    name: translate(STRING.FIELD_LABEL_EXAMPLE),
    tooltip: translate(STRING.TOOLTIP_VERIFY_EXAMPLE),
    renderCell: (item: Species) => {
      const example = item.verificationExample

      return (
        <ImageTableCell
          images={example?.imageUrl ? [{ src: example.imageUrl }] : []}
          theme={ImageCellTheme.Light}
          to={
            example
              ? getAppRoute({
                  to: APP_ROUTES.TAXA({ projectId }),
                  filters: { verifyOccurrence: String(example.id) },
                  keepSearchParams: true,
                })
              : undefined
          }
        />
      )
    },
  },
  {
    id: 'best-determination-score',
    name: translate(STRING.FIELD_LABEL_BEST_SCORE),
    sortField: 'best_determination_score',
    renderCell: (item: Species) => {
      const cell = (
        <BasicTableCell>
          <DeterminationScore
            score={item.score}
            scoreLabel={item.scoreLabel}
            tooltip={translate(STRING.MACHINE_PREDICTION_SCORE, {
              score: `${item.score}`,
            })}
          />
        </BasicTableCell>
      )

      return item.bestScoringOccurrenceId ? (
        <Link
          to={getAppRoute({
            to: APP_ROUTES.TAXA({ projectId }),
            filters: {
              verifyOccurrence: String(item.bestScoringOccurrenceId),
            },
            keepSearchParams: true,
          })}
        >
          {cell}
        </Link>
      ) : (
        cell
      )
    },
  },
  {
    id: 'created-at',
    name: translate(STRING.FIELD_LABEL_CREATED_AT),
    sortField: 'created_at',
    renderCell: (item: Species) => <DateTableCell date={item.createdAt} />,
  },
  {
    id: 'updated-at',
    name: translate(STRING.FIELD_LABEL_UPDATED_AT),
    sortField: 'updated_at',
    renderCell: (item: Species) => <DateTableCell date={item.updatedAt} />,
  },
]
