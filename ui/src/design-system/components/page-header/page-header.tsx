import classNames from 'classnames'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { IconButton, IconButtonTheme } from '../icon-button/icon-button'
import { IconType } from '../icon/icon'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import { Tooltip } from '../tooltip/tooltip'
import styles from './page-header.module.scss'

interface PageHeaderProps {
  isFetching?: boolean
  isLoading?: boolean
  subTitle: string
  title: string
  tooltip?: string
  children?: ReactNode
}

export const PageHeader = ({
  isFetching,
  isLoading,
  subTitle,
  title,
  tooltip,
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
      </div>
    </div>
    <div className={styles.row}>{children}</div>
  </div>
)
