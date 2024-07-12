import { AppliedFilters } from 'components/applied-filters/applied-filters'
import { ReactNode } from 'react'
import { STRING, translate } from 'utils/language'
import { LoadingSpinner } from '../loading-spinner/loading-spinner'
import styles from './page-header.module.scss'

interface PageHeaderProps {
  title: string
  subTitle: string
  isLoading?: boolean
  isFetching?: boolean
  showAppliedFilters?: boolean
  children?: ReactNode
}

export const PageHeader = ({
  title,
  subTitle,
  isLoading,
  isFetching,
  showAppliedFilters,
  children,
}: PageHeaderProps) => (
  <div className={styles.wrapper}>
    <div>
      <h1 className={styles.title}>{title}</h1>
      <div className={styles.row}>
        <h2 className={styles.subTitle}>
          {isLoading ? `${translate(STRING.LOADING_DATA)}...` : subTitle}
        </h2>
        {showAppliedFilters && <AppliedFilters />}
        {!isLoading && isFetching && <LoadingSpinner size={12} />}
      </div>
    </div>
    <div className={styles.row}>{children}</div>
  </div>
)
