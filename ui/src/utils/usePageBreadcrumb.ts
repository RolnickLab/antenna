import { useContext, useEffect } from 'react'
import { Breadcrumb, BreadcrumbContext } from './breadcrumbContext'

export const usePageBreadcrumb = (breadcrumb: Breadcrumb) => {
  const { setPageBreadcrumb } = useContext(BreadcrumbContext)

  useEffect(() => {
    setPageBreadcrumb(breadcrumb)

    return () => {
      setPageBreadcrumb(undefined)
    }
  }, [])
}
