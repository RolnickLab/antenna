import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useFilters } from 'utils/useFilters'
import styles from './applied-filters.module.scss'

export const AppliedFilters = () => {
  const { filters, clearFilter } = useFilters()

  return (
    <>
      {filters
        .filter((filter) => filter.value?.length)
        .map((filter) => (
          <div key={filter.field} className={styles.appliedFilter}>
            <span>
              {filter.label} {filter.value}
            </span>
            <IconButton
              customClass={styles.clearButton}
              icon={IconType.Cross}
              theme={IconButtonTheme.Plain}
              onClick={() => clearFilter(filter.field)}
            />
          </div>
        ))}
    </>
  )
}
