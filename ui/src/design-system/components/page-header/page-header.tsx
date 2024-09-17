import classNames from 'classnames'
import { AppliedFilters } from 'components/applied-filters/applied-filters'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import { Tooltip } from '../tooltip/tooltip'
import styles from './page-header.module.scss'

interface PageHeaderProps {
  title: string
  subTitle: string
  tooltip?: string
  isLoading?: boolean
  isFetching?: boolean
  showAppliedFilters?: boolean
  children?: ReactNode
}

export const PageHeader = ({
  title,
  subTitle,
  tooltip,
  isLoading,
  isFetching,
  showAppliedFilters,
  children,
}: PageHeaderProps) => (
  <div className={styles.wrapper}>
    <div>
      <div className={styles.row} style={{ gap: '4px' }}>
        <h1 className={styles.title}>{title}</h1>
        {tooltip ? (
          <Tooltip content={tooltip}>
            <IconButton icon={IconType.Info} theme={IconButtonTheme.Plain} />
          </Tooltip>
        ) : null}
      </div>
      <div className={classNames(styles.row, styles.details)}>
        <div className={styles.row}>
          <h2 className={styles.subTitle}>
            {isLoading ? `${translate(STRING.LOADING_DATA)}...` : subTitle}
          </h2>
          {!isLoading && isFetching && <LoadingSpinner size={12} />}
        </div>
        {showAppliedFilters && <AppliedFilters />}
      </div>
    </div>
    <div className={styles.row}>{children}</div>
  </div>
)
