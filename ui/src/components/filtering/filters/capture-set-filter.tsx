import { API_ROUTES, MAX_CAPTURE_SET_CHOICES } from 'data-services/constants'
import { EntityPicker } from 'nova-ui-kit'
import { FilterProps } from './types'

export const CaptureSetFilter = ({ onAdd, onClear, value }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.CAPTURE_SET_CHOICES}
    pageSize={MAX_CAPTURE_SET_CHOICES}
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
