import { API_ROUTES } from 'data-services/constants'
import { EntitiesPicker } from 'pages/project/entities/entities-picker'
import { FilterProps } from './types'

export const StationFilter = ({ value, onAdd }: FilterProps) => (
  <EntitiesPicker
    collection={API_ROUTES.DEPLOYMENTS}
    onValueChange={(value) => {
      if (value) {
        onAdd(value)
      }
    }}
    value={value}
  />
)
