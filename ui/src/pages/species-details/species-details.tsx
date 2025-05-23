import { BlueprintCollection } from 'components/blueprint-collection/blueprint-collection'
import { DeterminationScore } from 'components/determination-score'
import { Tag } from 'components/taxon-tags/tag'
import { TagsForm } from 'components/taxon-tags/tags-form'
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
import { UserPermission } from 'utils/user/types'
import styles from './species-details.module.scss'
import { SpeciesNameForm } from './species-name-form'
import { SpeciesParentForm } from './species-parent-form'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const canUpdate = species.userPermissions.includes(UserPermission.Update)
  const hasResources =
    !species.isUnknown || !!species.fieldguideUrl || canUpdate

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
        {species.isUnknown ? (
          <Tag name="Unknown species" className="bg-success" />
        ) : null}
      </div>
      <div className={styles.content}>
        <div className={styles.info}>
          <div className="grid gap-6">
            <InfoBlockField
              label={translate(STRING.FIELD_LABEL_NAME)}
              className="relative no-print"
            >
              <InfoBlockFieldValue value={species.name} />
              {species.isUnknown && canUpdate ? (
                <div className="absolute top-[-9px] right-0">
                  <SpeciesNameForm species={species} />
                </div>
              ) : null}
            </InfoBlockField>
            <InfoBlockField
              label={translate(STRING.FIELD_LABEL_PARENT)}
              className="relative no-print"
            >
              <InfoBlockFieldValue value={species.parentName} />
              {species.isUnknown && canUpdate ? (
                <div className="absolute top-[-9px] right-0">
                  <SpeciesParentForm species={species} />
                </div>
              ) : null}
            </InfoBlockField>
            <InfoBlockField
              label={translate(STRING.FIELD_LABEL_TAGS)}
              className="relative"
            >
              <div className="flex flex-col items-start gap-2 no-print">
                {species.tags.length ? (
                  <div className="flex flex-wrap gap-1">
                    {species.tags.map((tag) => (
                      <Tag key={tag.id} name={tag.name} />
                    ))}
                  </div>
                ) : (
                  <span>n/a</span>
                )}
                {canUpdate ? (
                  <div className="absolute top-[-9px] right-0">
                    <TagsForm species={species} />
                  </div>
                ) : null}
              </div>
            </InfoBlockField>
            <InfoBlockField label="Last seen">
              <InfoBlockFieldValue value={species.lastSeenLabel} />
            </InfoBlockField>
            <InfoBlockField label={translate(STRING.FIELD_LABEL_OCCURRENCES)}>
              <InfoBlockFieldValue
                value={
                  species.numOccurrences !== null
                    ? species.numOccurrences
                    : 'View all'
                }
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
            {hasResources ? (
              <InfoBlockField
                className={'no-print'}
                label={translate(STRING.RESOURCES)}
              >
                <div className="py-1 flex flex-col items-start gap-3">
                  {!species.isUnknown ? (
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
                  ) : null}
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
                  {canUpdate ? (
                    <Link
                      className={buttonVariants({
                        size: 'small',
                        variant: 'outline',
                      })}
                      to={species.djangoAdminUrl}
                      target="_blank"
                    >
                      <span>Django admin</span>
                      <ExternalLinkIcon className="w-4 h-4" />
                    </Link>
                  ) : null}
                </div>
              </InfoBlockField>
            ) : null}
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
