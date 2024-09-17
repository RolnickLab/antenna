import classNames from 'classnames'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Fragment, useContext, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Breadcrumb, BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import styles from './breadcrumbs.module.scss'

export const Breadcrumbs = ({
  navItems,
  activeNavItemId,
}: {
  navItems: { id: string; title: string; path?: string }[]
  activeNavItemId: string
}) => {
  const {
    pageBreadcrumb,
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

    return () => {
      setMainBreadcrumb(undefined)
    }
  }, [navItems, activeNavItemId])

  const breadcrumbs = [
    pageBreadcrumb,
    projectBreadcrumb,
    mainBreadcrumb,
    detailBreadcrumb,
  ].filter((breadcrumb) => !!breadcrumb) as Breadcrumb[]

  return (
    <div className={styles.breadcrumbs}>
      {breadcrumbs.map((breadcrumb, index) => {
        const isLast = index === breadcrumbs.length - 1
        const title = breadcrumb.title.length
          ? breadcrumb.title
          : `${translate(STRING.LOADING_DATA)}...`
        const compactTitle = '...'

        return (
          <Fragment key={index}>
            {isLast || !breadcrumb.path ? (
              <span className={styles.breadcrumb}>
                <span>{title}</span>
                <span>{compactTitle}</span>
              </span>
            ) : (
              <Link
                to={breadcrumb.path}
                className={classNames(styles.breadcrumb, styles.link)}
              >
                <span>{title}</span>
                <span>{compactTitle}</span>
              </Link>
            )}
            {!isLast && (
              <Icon
                type={IconType.ToggleRight}
                theme={IconTheme.Neutral}
                size={8}
              />
            )}
          </Fragment>
        )
      })}
    </div>
  )
}
