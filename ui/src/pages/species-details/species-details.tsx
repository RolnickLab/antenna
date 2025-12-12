import { BlueprintCollection } from 'components/blueprint-collection/blueprint-collection'
import { DeterminationScore } from 'components/determination-score'
import { Tag } from 'components/taxon-tags/tag'
import { TagsForm } from 'components/taxon-tags/tags-form'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import { Box } from 'design-system/components/box/box'
import {
  InfoBlockField,
  InfoBlockFieldValue,
} from 'design-system/components/info-block/info-block'
import { Plot } from 'design-system/components/plot/lazy-plot'
import * as Tabs from 'design-system/components/tabs/tabs'
import { ExternalLinkIcon, LockIcon } from 'lucide-react'
import { buttonVariants, TaxonDetails } from 'nova-ui-kit'
import { Helmet } from 'react-helmet-async'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import styles from './species-details.module.scss'

export const TABS = {
  FIELDS: 'fields',
  CHARTS: 'charts',
}

export const SpeciesDetails = ({
  species,
  selectedTab,
  setSelectedTab,
}: {
  species: Species
  selectedTab?: string
  setSelectedTab: (selectedTab?: string) => void
}) => {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const { project } = useProjectDetails(projectId as string, true)
  const canUpdate = species.userPermissions.includes(UserPermission.Update)
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
        {canUpdate ? (
          <div className="absolute bottom-6 right-6">
            <Link
              className={buttonVariants({
                size: 'small',
                variant: 'outline',
              })}
              to={species.adminUrl}
              target="_blank"
            >
              <LockIcon className="w-4 h-4" />
              <span>{translate(STRING.ADMIN)}</span>
            </Link>
          </div>
        ) : null}
      </div>
      <div className={styles.content}>
        <div className={styles.info}>
          <Tabs.Root value={selectedTab} onValueChange={setSelectedTab}>
            <Tabs.List>
              <Tabs.Trigger
                value={TABS.FIELDS}
                label={translate(STRING.TAB_ITEM_FIELDS)}
              />
              <Tabs.Trigger
                value={TABS.CHARTS}
                label={translate(STRING.TAB_ITEM_CHARTS)}
              />
            </Tabs.List>
            <Tabs.Content value={TABS.FIELDS}>
              <div className="grid gap-6">
                {project?.featureFlags.tags ? (
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
                ) : null}
                {species.commonNameLabel ? (
                  <InfoBlockField label="Common name (EN)">
                    <InfoBlockFieldValue value={species.commonNameLabel} />
                  </InfoBlockField>
                ) : null}
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
                <InfoBlockField
                  label={translate(STRING.FIELD_LABEL_BEST_SCORE)}
                >
                  <div>
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
                  </div>
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
                    {species.iNaturalistUrl ? (
                      <Link
                        className={buttonVariants({
                          size: 'small',
                          variant: 'outline',
                        })}
                        to={species.iNaturalistUrl}
                        target="_blank"
                      >
                        <span>iNaturalist</span>
                        <ExternalLinkIcon className="w-4 h-4" />
                      </Link>
                    ) : null}
                  </div>
                </InfoBlockField>
              </div>
            </Tabs.Content>
            <Tabs.Content value={TABS.CHARTS}>
              {species.summaryData.length ? (
                <div className="grid gap-6">
                  {species.summaryData.map((summary, index) => (
                    <Box key={index}>
                      <Plot
                        data={summary.data}
                        orientation={summary.orientation}
                        title={summary.title}
                        type={summary.type}
                      />
                    </Box>
                  ))}
                </div>
              ) : null}
            </Tabs.Content>
          </Tabs.Root>
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
