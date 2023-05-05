import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { STRING, translate } from 'utils/language'
import styles from './fetch-info.module.scss'

export const FetchInfo = ({ message: _message }: { message?: string }) => {
  const message = _message ?? `${translate(STRING.LOADING_DATA)}...`

  return (
    <div className={styles.wrapper}>
      <LoadingSpinner size={12} />
      <span>{message}</span>
    </div>
  )
}
