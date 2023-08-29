import classNames from 'classnames'
import { Icon, IconTheme, IconType } from '../../icon/icon'
import { IdentificationBreadcrumbs } from '../identification-breadcrumbs/identification-breadcrumbs'
import styles from './identification-summary.module.scss'

interface IdentificationSummaryProps {
  nodes: {
    id: string
    title: string
  }[]
  result: {
    id: string
    overridden?: boolean
    title: string
  }
  user?: {
    username: string
    profileImage?: string
  }
}

export const IdentificationSummary = ({
  nodes,
  result,
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
        [styles.overridden]: result.overridden,
      })}
    >
      {result.title}
    </span>
    <IdentificationBreadcrumbs nodes={nodes} />
  </div>
)
