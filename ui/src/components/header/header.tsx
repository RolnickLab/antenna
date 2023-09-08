import { InfoDialog } from 'components/info-dialog/info-dialog'
import { useLogout } from 'data-services/hooks/auth/useLogout'
import { usePages } from 'data-services/hooks/pages/usePages'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Link, useNavigate } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { useUser } from 'utils/user/userContext'
import ami from './ami.png'
import styles from './header.module.scss'
import { UserInfo } from './user-info/user-info'

export const Header = () => {
  const navigate = useNavigate()
  const { pages = [] } = usePages()
  const { user } = useUser()
  const { logout, isLoading: isLogoutLoading } = useLogout()

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
      <div className={styles.infoPages}>
        {pages.map((page) => (
          <InfoDialog key={page.id} name={page.name} slug={page.slug} />
        ))}
        <Button
          label="Sign up"
          theme={ButtonTheme.Plain}
          onClick={() => navigate(APP_ROUTES.SIGN_UP)}
        />
        {user.loggedIn ? (
          <>
            <Button
              label="Logout"
              theme={ButtonTheme.Plain}
              loading={isLogoutLoading}
              onClick={logout}
            />
            <UserInfo />
          </>
        ) : (
          <Button
            label="Login"
            theme={ButtonTheme.Plain}
            onClick={() => navigate(APP_ROUTES.LOGIN)}
          />
        )}
      </div>
    </header>
  )
}
