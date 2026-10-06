import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'nova-ui-kit'
import { FilterProps } from './types'

export const SiteFilter = ({ onAdd, onClear, value }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.SITES}
    onValueChange={(value) => {
      if (value) {
        onAdd(value)
      } else {
        onClear()
      }
    }}
    value={value}
  />
)
