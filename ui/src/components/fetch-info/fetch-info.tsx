import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { STRING, translate } from 'utils/language'
import styles from './fetch-info.module.scss'

enum FetchInfoType {
  Loading = 'loading',
  Updating = 'updating',
}

const messages: { [key in FetchInfoType]: string } = {
  [FetchInfoType.Loading]: translate(STRING.LOADING_DATA),
  [FetchInfoType.Updating]: translate(STRING.UPDATING_DATA),
}

export const FetchInfo = ({ isLoading }: { isLoading?: boolean }) => {
  const type = isLoading ? FetchInfoType.Loading : FetchInfoType.Updating

  return (
    <div className={styles.wrapper}>
      <LoadingSpinner size={12} />
      <span>{messages[type]}...</span>
    </div>
  )
}
