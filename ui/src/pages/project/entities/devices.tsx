import { API_ROUTES } from 'data-services/constants'
import { STRING, translate } from 'utils/language'
import { Entities } from './entities'

export const Devices = () => (
  <Entities
    title={translate(STRING.NAV_ITEM_DEVICES)}
    collection={API_ROUTES.DEVICES}
    type="device"
    tooltip={translate(STRING.TOOLTIP_DEVICE)}
  />
)
