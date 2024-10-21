import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useFilters } from 'utils/useFilters'
import styles from './applied-filters.module.scss'

interface AppliedFiltersProps {
  defaultFilters?: { field: string; value: string }[]
}

export const AppliedFilters = ({ defaultFilters }: AppliedFiltersProps) => {
  const { filters, clearFilter } = useFilters(defaultFilters)

  return (
    <>
      {filters
        .filter((filter) => filter.value?.length)
        .map((filter) => (
          <div key={filter.field} className={styles.appliedFilter}>
            <span>
              {filter.label} {filter.value}
            </span>
            {!defaultFilters?.some(
              (defaultFilter) =>
                defaultFilter.field === filter.field && defaultFilter.value
            ) && (
              <IconButton
                customClass={styles.clearButton}
                icon={IconType.Cross}
                theme={IconButtonTheme.Plain}
                onClick={() => clearFilter(filter.field)}
              />
            )}
          </div>
        ))}
    </>
  )
}
