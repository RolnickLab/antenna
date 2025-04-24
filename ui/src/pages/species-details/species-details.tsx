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
        <meta name="og:image" content={species.exampleOccurrence?.image_url} />
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
            <InfoBlockField label="Stations">
              <InfoBlockFieldValue value={species.stationsLabel} />
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
              </div>
            </InfoBlockField>
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection>
              {species.exampleOccurrence ? (
                <InfoBlockField label="Example occurrence">
                  <div className="flex justify-center bg-foreground">
                    <img src={species.exampleOccurrence.image_url} />
                  </div>
                  <span className="body-small whitespace-pre text-muted-foreground">
                    {species.exampleOccurrence.caption}
                  </span>
                </InfoBlockField>
              ) : null}
              <InfoBlockField label="Reference image">
                <img src={species.coverImage.url} />
                <span className="body-small text-muted-foreground">
                  {species.coverImage.copyright}
                </span>
              </InfoBlockField>
            </BlueprintCollection>
          </div>
        </div>
      </div>
    </div>
  )
}
