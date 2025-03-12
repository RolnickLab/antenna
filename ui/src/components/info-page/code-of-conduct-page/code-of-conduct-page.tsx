import { InfoPage } from '../info-page'
import markdown from './code-of-conduct.md'

export const CodeOfConductPage = () => (
  <InfoPage anchorPrefix="chapter" markdown={markdown} />
)
