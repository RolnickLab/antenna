import {
  BlueprintCollection,
  BlueprintItem,
} from 'components/blueprint-collection/blueprint-collection'
import { SpeciesDetails as Species } from 'data-services/models/species-details'
import {
  InfoBlockField,
  InfoBlockFieldValue,
} from 'design-system/components/info-block/info-block'
import { ExternalLinkIcon } from 'lucide-react'
import { buttonVariants, TaxonDetails } from 'nova-ui-kit'
import { useMemo } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './species-details.module.scss'

export const SpeciesDetails = ({ species }: { species: Species }) => {
  const { projectId } = useParams()
  const navigate = useNavigate()

  const image = useMemo(() => {
    if (species.occurrences.length) {
      const occurrenceInfo = species.getOccurrenceInfo(species.occurrences[0])
      return occurrenceInfo?.image.src
    }
  }, [species])

  const blueprintItems = useMemo(
    () =>
      species.occurrences.length
        ? species.occurrences
            .map((id) => species.getOccurrenceInfo(id))
            .filter((item): item is BlueprintItem => !!item)
            .map((item) => ({
              ...item,
              to: APP_ROUTES.OCCURRENCE_DETAILS({
                projectId: projectId as string,
                occurrenceId: item.id,
              }),
            }))
        : [],
    [species]
  )

  return (
    <div className={styles.wrapper}>
      <Helmet>
        <meta name="og:image" content={image} />
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
        <div className={styles.column}>
          <div className={styles.info}>
            <div className={styles.fields}>
              <div className="grid gap-6">
                <InfoBlockField
                  label={translate(STRING.FIELD_LABEL_OCCURRENCES)}
                >
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
                <InfoBlockField label={translate(STRING.EXTERNAL_RESOURCES)}>
                  <div className="py-1">
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
                  </div>
                </InfoBlockField>
              </div>
            </div>
          </div>
        </div>
        <div className={styles.blueprintWrapper}>
          <div className={styles.blueprintContainer}>
            <BlueprintCollection>
              {blueprintItems.map((item) => (
                <BlueprintItem key={item.id} item={item} />
              ))}
            </BlueprintCollection>
          </div>
        </div>
      </div>
    </div>
  )
}
