import { InfoPage } from '../info-page'
import markdown from './terms-of-service.md'

export const TermsOfServicePage = () => (
  <InfoPage anchorPrefix="term" markdown={markdown} />
)
