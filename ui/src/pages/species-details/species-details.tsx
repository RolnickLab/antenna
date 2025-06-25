import { BlueprintCollection } from 'components/blueprint-collection/blueprint-collection'
import { DeterminationScore } from 'components/determination-score'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import {
  InfoBlockField,
  InfoBlockFieldValue,
} from 'design-system/components/info-block/info-block'
import { ExternalLinkIcon } from 'lucide-react'
import { buttonVariants, TaxonDetails } from 'nova-ui-kit'
import { Helmet } from 'react-helmet-async'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const hasChildren = species.rank !== 'SPECIES'

  return (
    <div className={styles.wrapper}>
      <Helmet>
        <meta name="og:image" content={species.exampleOccurrence?.url} />
      </Helmet>
      <div className={styles.header}>
        <TaxonDetails
          onTaxonClick={(id) =>
            navigate(
              getAppRoute({
                to: APP_ROUTES.TAXON_DETAILS({
                  projectId: projectId as string,
                  taxonId: id,
                }),
              })
            )
          }
          size="lg"
          taxon={species}
        />
      </div>
      <div className={styles.content}>
        <div className={styles.info}>
          <div className="grid gap-6">
            <InfoBlockField label="Last seen">
              <InfoBlockFieldValue value={species.lastSeenLabel} />
            </InfoBlockField>
            {hasChildren ? (
              <InfoBlockField label="Child taxa">
                <InfoBlockFieldValue
                  value="View all"
                  to={getAppRoute({
                    to: APP_ROUTES.TAXA({
                      projectId: projectId as string,
                    }),
                    filters: { taxon: species.id },
                  })}
                />
              </InfoBlockField>
            ) : null}
            <InfoBlockField label="Occurrences">
              <InfoBlockFieldValue
                value={`Direct: ${species.numOccurrences ?? 0}`}
              />
              <InfoBlockFieldValue
                value="View all"
                to={getAppRoute({
                  to: APP_ROUTES.OCCURRENCES({
                    projectId: projectId as string,
                  }),
                  filters: { taxon: species.id },
                })}
              />
            </InfoBlockField>
            <InfoBlockField label={translate(STRING.FIELD_LABEL_BEST_SCORE)}>
              <DeterminationScore
                score={species.score}
                scoreLabel={species.scoreLabel}
                tooltip={
                  species.score
                    ? translate(STRING.MACHINE_PREDICTION_SCORE, {
                        score: `${species.score}`,
                      })
                    : undefined
                }
              />
            </InfoBlockField>
            <InfoBlockField
              className="no-print"
              label={translate(STRING.EXTERNAL_RESOURCES)}
            >
              <div className="py-1 flex items-center gap-3">
                <Link
                  className={buttonVariants({
                    size: 'small',
                    variant: 'outline',
                  })}
                  to={species.gbifUrl}
                  target="_blank"
                >
                  <span>GBIF</span>
                  <ExternalLinkIcon className="w-4 h-4" />
                </Link>
                {species.fieldguideUrl ? (
                  <Link
                    className={buttonVariants({
                      size: 'small',
                      variant: 'outline',
                    })}
                    to={species.fieldguideUrl}
                    target="_blank"
                  >
                    <span>Fieldguide</span>
                    <ExternalLinkIcon className="w-4 h-4" />
                  </Link>
                ) : null}
              </div>
            </InfoBlockField>
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection>
              {species.coverImage &&
              species.coverImage.url !== species.exampleOccurrence?.url ? (
                <InfoBlockField label="Reference image">
                  <a
                    href={species.coverImage.url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <img src={species.coverImage.url} />
                  </a>
                  <span className="body-small text-muted-foreground">
                    {species.coverImage.caption}
                  </span>
                </InfoBlockField>
              ) : null}
              {species.exampleOccurrence ? (
                <InfoBlockField label="Example occurrence">
                  <Link
                    to={getAppRoute({
                      to: APP_ROUTES.OCCURRENCE_DETAILS({
                        projectId: projectId as string,
                        occurrenceId: species.exampleOccurrence.id,
                      }),
                    })}
                  >
                    <img src={species.exampleOccurrence.url} />
                  </Link>
                  {species.exampleOccurrence.caption ? (
                    <span className="body-small text-muted-foreground">
                      {species.exampleOccurrence.caption}
                    </span>
                  ) : undefined}
                </InfoBlockField>
              ) : null}
            </BlueprintCollection>
          </div>
        </div>
      </div>
    </div>
  )
}
