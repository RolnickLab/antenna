import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'nova-ui-kit'
import { FilterProps } from './types'

export const StationFilter = ({ onAdd, onClear, value }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.DEPLOYMENTS}
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
