import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'nova-ui-kit'
import { FilterProps } from './types'

// Stations can use a shared record with no project, so list what the project's stations use.
const STATION_REFS_IN_USE = [{ field: 'has_deployments', value: 'true' }]

export const DeviceFilter = ({ onAdd, onClear, value }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.DEVICES}
    filters={STATION_REFS_IN_USE}
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
