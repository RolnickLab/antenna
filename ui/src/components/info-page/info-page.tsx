import { usePageDetails } from 'data-services/hooks/pages/usePageDetails'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Error } from 'pages/error/error'
import styles from './info-page.module.scss'
import { TERMS_OF_SERVICE_SLUG } from './terms-of-service-page/constants'
import { TermsOfServicePage } from './terms-of-service-page/terms-of-service-page'

export const InfoPage = ({ slug }: { slug: string }) => {
  if (slug === TERMS_OF_SERVICE_SLUG) {
    return <TermsOfServicePage />
  }

  return <InfoPageContent slug={slug} />
}

const InfoPageContent = ({ slug }: { slug: string }) => {
  const { page, isLoading, error } = usePageDetails(slug)

  if (isLoading) {
    return (
      <div className={styles.wrapper}>
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={styles.wrapper}>
        <Error error={error} />
      </div>
    )
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.container}>
        {page ? (
          <div
            dangerouslySetInnerHTML={{ __html: page.html }}
            className={styles.content}
          />
        ) : null}
      </div>
    </div>
  )
}
