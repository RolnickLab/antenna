import { API_ROUTES } from 'data-services/constants'
import { EntitiesPicker } from 'pages/project/entities/entities-picker'
import { FilterProps } from './types'

export const AlgorithmFilter = ({
  value,
  onAdd,
}: FilterProps & { placeholder?: string }) => (
  <EntitiesPicker
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
