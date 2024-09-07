import { useLogout } from 'data-services/hooks/auth/useLogout'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePageTitle } from 'utils/usePageTitle'
import { useUser } from 'utils/user/userContext'
import ami from './ami.png'
import styles from './header.module.scss'
import { UserInfoDialog } from './user-info-dialog/user-info-dialog'
import { VersionInfo } from './version-info/version-info'

export const Header = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useUser()
  const { logout, isLoading: isLogoutLoading } = useLogout()

  usePageTitle()

  return (
    <header className={styles.header}>
      <Link to="/">
        <img
          alt="AMI"
          src={ami}
          width={40}
          height={40}
          className={styles.logo}
        />
      </Link>
      <VersionInfo />
      <div className={styles.rightContent}>
        <div className={styles.infoPages}>
          <Button
            label="Terms of Service"
            theme={ButtonTheme.Plain}
            onClick={() => navigate(APP_ROUTES.TERMS_OF_SERVICE)}
          />
        </div>
        {user.loggedIn ? (
          <>
            <Button
              label={translate(STRING.LOGOUT)}
              theme={ButtonTheme.Plain}
              loading={isLogoutLoading}
              onClick={() => logout()}
            />
            <UserInfoDialog />
          </>
        ) : (
          <>
            <Button
              label={translate(STRING.LOGIN)}
              theme={ButtonTheme.Plain}
              onClick={() =>
                navigate(APP_ROUTES.LOGIN, { state: { to: location.pathname } })
              }
            />
          </>
        )}
      </div>
    </header>
  )
}
