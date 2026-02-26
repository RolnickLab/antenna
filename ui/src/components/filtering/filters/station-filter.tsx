import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'design-system/components/select/entity-picker'
import { FilterProps } from './types'

export const StationFilter = ({ value, onAdd }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.DEPLOYMENTS}
    onValueChange={(value) => {
      if (value) {
        onAdd(value)
      }
    }}
    value={value}
  />
)
