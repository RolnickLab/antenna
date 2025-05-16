import classNames from 'classnames'
import { BlueprintCollection } from 'components/blueprint-collection/blueprint-collection'
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

  return (
    <div className={styles.wrapper}>
      <Helmet>
        <meta name="og:image" content={species.thumbnailUrl} />
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
          <div className={classNames(styles.badge, 'no-print')}>
            Unknown species
          </div>
        ) : null}
      </div>
      <div className={styles.content}>
        <div className={styles.info}>
          <div className="grid gap-6">
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
            {species.isUnknown ? (
              <InfoBlockField label="Most similar known taxon">
                <InfoBlockFieldValue value={undefined} />
              </InfoBlockField>
            ) : (
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
            )}
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection>
              {Object.entries(species.images).map(([key, image]) => (
                <InfoBlockField key={key} label={image.title}>
                  {image.sizes.original ? (
                    <>
                      <a
                        href={image.sizes.original}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <img src={image.sizes.original} />
                      </a>
                      {image.caption ? (
                        <span className="body-small text-muted-foreground">
                          {image.caption}
                        </span>
                      ) : null}
                    </>
                  ) : (
                    <InfoBlockFieldValue />
                  )}
                </InfoBlockField>
              ))}
            </BlueprintCollection>
          </div>
        </div>
      </div>
    </div>
  )
}
