import classNames from 'classnames'
import { useLogout } from 'data-services/hooks/auth/useLogout'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import buttonStyles from 'design-system/components/button/button.module.scss'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Helmet } from 'react-helmet-async'
import { Link, useLocation } from 'react-router-dom'
import { APP_ROUTES, LANDING_PAGE_URL } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePageTitle } from 'utils/usePageTitle'
import { useUser } from 'utils/user/userContext'
import antenna from './antenna-primary.svg'
import styles from './header.module.scss'
import { UserInfoDialog } from './user-info-dialog/user-info-dialog'
import { VersionInfo } from './version-info/version-info'

export const Header = () => {
  const location = useLocation()
  const { user } = useUser()
  const { logout, isLoading: isLogoutLoading } = useLogout()
  const pageTitle = usePageTitle()

  return (
    <header className={styles.header}>
      <Helmet>
        <title>{pageTitle}</title>
      </Helmet>
      <Link to="/" className={styles.logoContainer}>
        <img
          alt="Antenna"
          src={antenna}
          width={40}
          height={40}
          className={styles.logo}
        />
      </Link>
      <VersionInfo />
      <div className={styles.rightContent}>
        <div className={styles.infoPages}>
          <a
            href={LANDING_PAGE_URL}
            rel="noreferrer"
            target="_blank"
            className={classNames(buttonStyles.button, buttonStyles.plain)}
          >
            <span className={buttonStyles.label}>About Antenna</span>
            <Icon
              type={IconType.ExternalLink}
              theme={IconTheme.Primary}
              size={14}
            />
          </a>
          <Link
            to={APP_ROUTES.TERMS_OF_SERVICE}
            className={classNames(buttonStyles.button, buttonStyles.plain)}
          >
            <span className={buttonStyles.label}>Terms of Service</span>
          </Link>
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
          <Link
            to={APP_ROUTES.LOGIN}
            state={{
              to: {
                pathname: location.pathname,
                search: location.search,
              },
            }}
            className={classNames(buttonStyles.button, buttonStyles.plain)}
          >
            <span className={buttonStyles.label}>
              {translate(STRING.LOGIN)}
            </span>
          </Link>
        )}
      </div>
    </header>
  )
}
