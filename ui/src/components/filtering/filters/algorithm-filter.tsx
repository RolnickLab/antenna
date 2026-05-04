import { API_ROUTES } from 'data-services/constants'
import { EntityPicker } from 'design-system/components/select/entity-picker'
import { FilterProps } from './types'

export const AlgorithmFilter = ({
  value,
  onAdd,
}: FilterProps & { placeholder?: string }) => (
  <EntityPicker
    collection={API_ROUTES.ALGORITHM}
    onValueChange={(value) => {
      if (value) {
        onAdd(value)
      }
    }}
    value={value}
  />
)

export const NotAlgorithmFilter = (props: FilterProps) => (
  <AlgorithmFilter {...props} />
)
