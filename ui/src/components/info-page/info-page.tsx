import { TERMS_OF_SERVICE_SLUG } from './terms-of-service-page/constants'
import { TermsOfServicePage } from './terms-of-service-page/terms-of-service-page'

export const InfoPage = ({ slug }: { slug: string }) => {
  if (slug === TERMS_OF_SERVICE_SLUG) {
    return <TermsOfServicePage />
  }

  return null
}
