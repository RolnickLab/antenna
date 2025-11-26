import classNames from 'classnames'
import { InfoIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import { BasicTooltip } from '../tooltip/basic-tooltip'
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
          <BasicTooltip asChild content={tooltip}>
            <Button size="icon" variant="ghost">
              <InfoIcon className="w-4 h-4" />
            </Button>
          </BasicTooltip>
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
    <div className={classNames(styles.row, 'no-print')}>{children}</div>
  </div>
)
