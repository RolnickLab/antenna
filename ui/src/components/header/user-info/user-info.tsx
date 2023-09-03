import { useMe } from 'data-services/hooks/auth/useMe'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './user-info.module.scss'

export const UserInfo = () => {
  const { user } = useMe()

  if (!user) {
    return null
  }

  const name = user.name ?? user.email

  return (
    <Tooltip content={name}>
      <div className={styles.userInfo}>{name.charAt(0)}</div>
    </Tooltip>
  )
}
