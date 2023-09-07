import { useUserInfo } from 'data-services/hooks/auth/useUserInfo'
import * as Dialog from 'design-system/components/dialog/dialog'
import { STRING, translate } from 'utils/language'
import { UserInfoForm } from './user-info-form/user-info-form'
import styles from './user-info.module.scss'

export const UserInfo = () => {
  const { userInfo } = useUserInfo()

  if (!userInfo) {
    return null
  }

  const name = userInfo.name ?? userInfo.email

  return (
    <>
      <Dialog.Root>
        <Dialog.Trigger>
          <div
            role="button"
            tabIndex={0}
            className={styles.userInfo}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                e.currentTarget.click()
              }
            }}
          >
            {name.charAt(0)}
          </div>
        </Dialog.Trigger>
        <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
          <Dialog.Header title="Edit user info" />
          <div className={styles.content}>
            <UserInfoForm userInfo={userInfo} />
          </div>
        </Dialog.Content>
      </Dialog.Root>
    </>
  )
}
