import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Fragment, useContext, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Breadcrumb, BreadcrumbContext } from 'utils/breadcrumbContext'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import styles from './breadcrumbs.module.scss'

export const Breadcrumbs = ({
  navItems,
  activeNavItemId,
}: {
  navItems: { id: string; title: string; path: string }[]
  activeNavItemId: string
}) => {
  const {
    projectBreadcrumb,
    mainBreadcrumb,
    detailBreadcrumb,
    setMainBreadcrumb,
  } = useContext(BreadcrumbContext)

  useEffect(() => {
    const activeNavItem =
      activeNavItemId !== 'overview' &&
      navItems.find((navItem) => navItem.id === activeNavItemId)

    setMainBreadcrumb(
      activeNavItem
        ? { title: activeNavItem.title, path: activeNavItem.path }
        : undefined
    )
  }, [navItems, activeNavItemId])

  const breadcrumbs = [
    { title: translate(STRING.NAV_ITEM_PROJECTS), path: APP_ROUTES.HOME },
    projectBreadcrumb,
    mainBreadcrumb,
    detailBreadcrumb,
  ].filter((breadcrumb) => !!breadcrumb) as Breadcrumb[]

  return (
    <div className={styles.breadcrumbs}>
      {breadcrumbs.map((breadcrumb, index) => {
        if (index === breadcrumbs.length - 1) {
          return (
            <span key={index} className={styles.breadcrumb}>
              {breadcrumb.title}
            </span>
          )
        }
        return (
          <Fragment key={index}>
            <Link
              to={breadcrumb.path}
              className={classNames(styles.breadcrumb, styles.link)}
            >
              <span>{breadcrumb.title}</span>
            </Link>
            <Icon
              type={IconType.ToggleRight}
              theme={IconTheme.Neutral}
              size={8}
            />
          </Fragment>
        )
      })}
    </div>
  )
}
