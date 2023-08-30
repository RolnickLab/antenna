import classNames from 'classnames'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import { IdentificationBreadcrumbs } from '../identification-breadcrumbs/identification-breadcrumbs'
import styles from './identification-summary.module.scss'

interface IdentificationSummaryProps {
  identification: {
    id: string
    overridden?: boolean
    title: string
  }
  ranks: {
    id: string
    title: string
  }[]
  user?: {
    username: string
    profileImage?: string
  }
}

export const IdentificationSummary = ({
  identification,
  ranks,
  user,
}: IdentificationSummaryProps) => (
  <div>
    <div className={styles.user}>
      {user ? (
        <div className={styles.profileImage}>
          {user.profileImage ? (
            <img src={user.profileImage} alt="User profile image" />
          ) : (
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Primary}
              size={16}
            />
          )}
        </div>
      ) : (
        <Icon type={IconType.BatchId} theme={IconTheme.Primary} size={16} />
      )}
      <span className={styles.username}>
        {user?.username ?? 'Machine suggestion'}
      </span>
    </div>
    <span
      className={classNames(styles.title, {
        [styles.overridden]: identification.overridden,
      })}
    >
      {identification.title}
    </span>
    <IdentificationBreadcrumbs items={ranks} />
  </div>
)
