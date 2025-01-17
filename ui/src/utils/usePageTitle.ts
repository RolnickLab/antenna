import { useContext, useEffect, useState } from 'react'
import { BreadcrumbContext } from './breadcrumbContext'

const DEFAULT_PAGE_TITLE = 'Antenna Data Platform'
const SEPARATOR = ' | '

export const usePageTitle = () => {
  const [pageTitle, setPageTitle] = useState(DEFAULT_PAGE_TITLE)
  const {
    pageBreadcrumb,
    projectBreadcrumb,
    mainBreadcrumb,
    detailBreadcrumb,
  } = useContext(BreadcrumbContext)

  useEffect(() => {
    const breadcrumbs = [
      { title: DEFAULT_PAGE_TITLE },
      ...(projectBreadcrumb
        ? [projectBreadcrumb, mainBreadcrumb, detailBreadcrumb]
        : [pageBreadcrumb]),
    ]

    const pageTitle = breadcrumbs
      .filter((breadcrumb) => breadcrumb?.title.length)
      .map((breadcrumb) => breadcrumb?.title as string)
      .reverse()
      .join(SEPARATOR)

    setPageTitle(pageTitle)
  }, [pageBreadcrumb, projectBreadcrumb, mainBreadcrumb, detailBreadcrumb])

  return pageTitle
}
