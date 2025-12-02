import * as Dialog from 'design-system/components/dialog/dialog'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'
import styles from './user-info-dialog.module.scss'
import { UserInfoForm } from './user-info-form/user-info-form'

export const UserInfoDialog = () => {
  const { userInfo } = useUserInfo()

  if (!userInfo) {
    return null
  }

  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
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
          <UserInfoButtonContent userInfo={userInfo} />
        </div>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header
          title={translate(STRING.ENTITY_EDIT, {
            type: translate(STRING.USER_INFO).toLowerCase(),
          })}
        />
        <div className={styles.content}>
          <UserInfoForm userInfo={userInfo} />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const UserInfoButtonContent = ({ userInfo }: { userInfo: UserInfo }) => {
  const name = (() => {
    if (userInfo.name?.length) {
      return userInfo.name
    }
    if (userInfo.email?.length) {
      return userInfo.email
    }
    return '?'
  })()

  if (userInfo.image) {
    return <img alt="" src={userInfo.image} />
  }

  return <span>{name.charAt(0)}</span>
}
