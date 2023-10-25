import { createContext, ReactNode, useState } from 'react'

export interface Breadcrumb {
  title: string
  path?: string
}

interface BreadcrumbContextValues {
  pageBreadcrumb?: Breadcrumb
  projectBreadcrumb?: Breadcrumb
  mainBreadcrumb?: Breadcrumb
  detailBreadcrumb?: Breadcrumb
  setPageBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setProjectBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setMainBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setDetailBreadcrumb: (breadcrumb?: Breadcrumb) => void
}

export const BreadcrumbContext = createContext<BreadcrumbContextValues>({
  pageBreadcrumb: undefined,
  projectBreadcrumb: undefined,
  mainBreadcrumb: undefined,
  detailBreadcrumb: undefined,
  setPageBreadcrumb: () => {},
  setProjectBreadcrumb: () => {},
  setMainBreadcrumb: () => {},
  setDetailBreadcrumb: () => {},
})

export const BreadcrumbContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [pageBreadcrumb, setPageBreadcrumb] = useState<Breadcrumb>()
  const [projectBreadcrumb, setProjectBreadcrumb] = useState<Breadcrumb>()
  const [mainBreadcrumb, setMainBreadcrumb] = useState<Breadcrumb>()
  const [detailBreadcrumb, setDetailBreadcrumb] = useState<Breadcrumb>()

  return (
    <BreadcrumbContext.Provider
      value={{
        pageBreadcrumb,
        projectBreadcrumb,
        mainBreadcrumb,
        detailBreadcrumb,
        setPageBreadcrumb,
        setProjectBreadcrumb,
        setMainBreadcrumb,
        setDetailBreadcrumb,
      }}
    >
      {children}
    </BreadcrumbContext.Provider>
  )
}
