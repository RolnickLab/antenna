import classNames from 'classnames'
import { ChevronRightIcon } from 'lucide-react'
import { Fragment, useContext, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Breadcrumb, BreadcrumbContext } from 'utils/breadcrumbContext'
import { STRING, translate } from 'utils/language'
import styles from './breadcrumbs.module.scss'

export const Breadcrumbs = ({
  activeNavItem,
  navItems,
}: {
  activeNavItem: { id: string; title: string; path?: string }
  navItems: { id: string; title: string; path?: string }[]
}) => {
  const {
    pageBreadcrumb,
    projectBreadcrumb,
    mainBreadcrumb,
    detailBreadcrumb,
    setMainBreadcrumb,
  } = useContext(BreadcrumbContext)

  useEffect(() => {
    if (activeNavItem.id !== 'project') {
      setMainBreadcrumb(activeNavItem)
    }

    return () => {
      setMainBreadcrumb(undefined)
    }
  }, [navItems, activeNavItem, setMainBreadcrumb])

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
              <ChevronRightIcon className="w-3 h-3 text-muted-foreground/50" />
            )}
          </Fragment>
        )
      })}
    </div>
  )
}
