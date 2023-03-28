import { IconButton } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import styles from './pagination-bar.module.scss'

const getValueInRange = (args: { value: number; min: number; max: number }) =>
  Math.min(args.max, Math.max(args.min, args.value))

interface PaginationBarProps {
  page: number
  perPage: number
  total: number
  onPrevClick: () => void
  onNextClick: () => void
}

export const PaginationBar = ({
  page,
  perPage,
  total,
  onPrevClick,
  onNextClick,
}: PaginationBarProps) => {
  const minIndex = 0
  const maxIndex = total - 1

  const startIndex = getValueInRange({
    value: page * perPage,
    min: minIndex,
    max: maxIndex,
  })
  const endIndex = getValueInRange({
    value: startIndex + perPage - 1,
    min: minIndex,
    max: maxIndex,
  })

  const prevDisabled = startIndex - 1 < minIndex
  const nextDisabled = endIndex + 1 > maxIndex

  const infoLabel = `Showing ${startIndex + 1}-${
    endIndex + 1
  } of ${total} results`

  return (
    <div className={styles.paginationBar}>
      <span>{infoLabel}</span>
      <div className={styles.paginationButtons}>
        <IconButton
          icon={IconType.ToggleLeft}
          disabled={prevDisabled}
          onClick={onPrevClick}
        />
        <IconButton
          icon={IconType.ToggleRight}
          disabled={nextDisabled}
          onClick={onNextClick}
        />
      </div>
    </div>
  )
}
