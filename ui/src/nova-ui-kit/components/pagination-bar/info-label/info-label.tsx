import { STRING, translate } from 'utils/language'
import { getValueInRange } from './getValueInRange'
import styles from './info-label.module.scss'

interface InfoLabelProps {
  pagination: {
    page: number
    perPage: number
  }
  total: number
}

export const InfoLabel = ({ pagination, total }: InfoLabelProps) => {
  const minIndex = 0
  const maxIndex = total - 1
  const startIndex = getValueInRange({
    value: pagination.page * pagination.perPage,
    min: minIndex,
    max: maxIndex,
  })
  const endIndex = getValueInRange({
    value: startIndex + pagination.perPage - 1,
    min: minIndex,
    max: maxIndex,
  })

  return (
    <span className={styles.infoLabel}>
      {translate(STRING.MESSAGE_RESULT_RANGE, {
        start: startIndex + 1,
        end: endIndex + 1,
        total,
      })}
    </span>
  )
}
