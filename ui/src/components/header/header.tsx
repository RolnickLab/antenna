import classNames from 'classnames'
import { useLogout } from 'data-services/hooks/auth/useLogout'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import {
  BookOpenIcon,
  ChevronDownIcon,
  ExternalLinkIcon,
  Loader2Icon,
} from 'lucide-react'
import { Button, buttonVariants, Popover } from 'nova-ui-kit'
import { Helmet } from 'react-helmet-async'
import { Link, useLocation } from 'react-router-dom'
import { APP_ROUTES, DOCS_URL, LANDING_PAGE_URL } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { usePageTitle } from 'utils/usePageTitle'
import { useUser } from 'utils/user/userContext'
import antennaHalloween from './antenna-halloween.svg'
import antennaPrimary from './antenna-primary.svg'
import styles from './header.module.scss'
import { UserInfoDialog } from './user-info-dialog/user-info-dialog'
import { VersionInfo } from './version-info/version-info'

const LOGOS: { [key: string]: { image: string; tooltip?: string } } = {
  default: {
    image: antennaPrimary,
  },
  halloween: {
    image: antennaHalloween,
    tooltip: 'Happy Halloween!',
  },
}
const LOGO = LOGOS[import.meta.env.VITE_ENV_LOGO] ?? LOGOS.default

const LINK_CLASSNAME = classNames(
  buttonVariants({ size: 'small', variant: 'ghost' }),
  'justify-between'
)

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
      <BasicTooltip asChild content={LOGO.tooltip}>
        <Link to="/" className={styles.logoContainer}>
          <img
            alt="Antenna"
            src={LOGO.image}
            width={40}
            height={40}
            className={styles.logo}
          />
        </Link>
      </BasicTooltip>
      <VersionInfo />
      <div className={styles.rightContent}>
        <div className={styles.infoPages}>
          <a
            className={LINK_CLASSNAME}
            href={DOCS_URL}
            rel="noreferrer"
            target="_blank"
          >
            <BookOpenIcon className="w-4 h-4" />
            <span>{translate(STRING.NAV_ITEM_DOCS)}</span>
          </a>
          <Popover.Root key={location.pathname}>
            <Popover.Trigger asChild>
              <Button size="small" variant="ghost">
                <span>{translate(STRING.NAV_ITEM_ABOUT)}</span>
                <ChevronDownIcon className="w-4 h-4" />
              </Button>
            </Popover.Trigger>
            <Popover.Content className="w-auto grid gap-1">
              <a
                className={LINK_CLASSNAME}
                href={LANDING_PAGE_URL}
                rel="noreferrer"
                target="_blank"
              >
                <span>{translate(STRING.NAV_ITEM_LANDING_PAGE)}</span>
                <ExternalLinkIcon className="w-4 h-4" />
              </a>
              <Link className={LINK_CLASSNAME} to={APP_ROUTES.TERMS_OF_SERVICE}>
                <span>{translate(STRING.NAV_ITEM_TERMS_OF_SERVICE)}</span>
              </Link>
              <Link className={LINK_CLASSNAME} to={APP_ROUTES.CODE_OF_CONDUCT}>
                <span>{translate(STRING.NAV_ITEM_CODE_OF_CONDUCT)}</span>
              </Link>
            </Popover.Content>
          </Popover.Root>
        </div>
        {user.loggedIn ? (
          <>
            <Button
              disabled={isLogoutLoading}
              onClick={() => logout()}
              size="small"
              variant="ghost"
            >
              <span>{translate(STRING.LOGOUT)}</span>
              {isLogoutLoading ? (
                <Loader2Icon className="w-4 h-4 animate-spin" />
              ) : null}
            </Button>
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
            className={LINK_CLASSNAME}
          >
            <span>{translate(STRING.LOGIN)}</span>
          </Link>
        )}
      </div>
    </header>
  )
}
