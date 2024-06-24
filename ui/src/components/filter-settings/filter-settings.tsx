import { Button } from 'design-system/components/button/button'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import * as Popover from 'design-system/components/popover/popover'
import { STRING, translate } from 'utils/language'
import { useFilters } from 'utils/useFilters'
import styles from './filter-settings.module.scss'

export const FilterSettings = () => {
  const { filters, isActive, clearAll } = useFilters()

  return (
    <Popover.Root>
      <Popover.Trigger>
        <IconButton
          icon={IconType.Filters}
          theme={isActive ? IconButtonTheme.Neutral : IconButtonTheme.Default}
        />
      </Popover.Trigger>
      <Popover.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        align="end"
        side="bottom"
      >
        <div className={styles.wrapper}>
          <span className={styles.description}>Filters</span>
          <div className={styles.filters}>
            {isActive ? (
              filters
                .filter((filter) => filter.value?.length)
                .map((filter) => {
                  return (
                    <span className={styles.filterLabel} key={filter.field}>
                      {filter.label}: {filter.value}
                    </span>
                  )
                })
            ) : (
              <span className={styles.filterLabel}>No filters active.</span>
            )}
          </div>
          <Button label="Clear all" disabled={!isActive} onClick={clearAll} />
        </div>
      </Popover.Content>
    </Popover.Root>
  )
}
