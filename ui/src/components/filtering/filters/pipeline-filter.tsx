import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'design-system/components/select/entity-picker'
import { FilterProps } from './types'

export const PipelineFilter = ({ onAdd, onClear, value }: FilterProps) => (
  <EntityPicker
    collection={API_ROUTES.PIPELINES}
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
