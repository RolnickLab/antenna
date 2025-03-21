import { API_ROUTES } from 'data-services/constants'
import { STRING, translate } from 'utils/language'
import { Entities } from './entities'

export const Sites = () => (
  <Entities
    title={translate(STRING.NAV_ITEM_SITES)}
    collection={API_ROUTES.SITES}
    type="site"
    tooltip={translate(STRING.TOOLTIP_SITE)}
  />
)
