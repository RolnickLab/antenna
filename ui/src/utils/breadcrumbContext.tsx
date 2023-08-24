/* eslint-disable @typescript-eslint/no-empty-function */

import { createContext, ReactNode, useState } from 'react'

export interface Breadcrumb {
  title: string
  path: string
}

interface BreadcrumbContextValues {
  projectBreadcrumb?: Breadcrumb
  mainBreadcrumb?: Breadcrumb
  detailBreadcrumb?: Breadcrumb
  setProjectBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setMainBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setDetailBreadcrumb: (breadcrumb?: Breadcrumb) => void
}

export const BreadcrumbContext = createContext<BreadcrumbContextValues>({
  projectBreadcrumb: undefined,
  mainBreadcrumb: undefined,
  detailBreadcrumb: undefined,
  setProjectBreadcrumb: () => {},
  setMainBreadcrumb: () => {},
  setDetailBreadcrumb: () => {},
})

export const BreadcrumbContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [projectBreadcrumb, setProjectBreadcrumb] = useState<Breadcrumb>()
  const [mainBreadcrumb, setMainBreadcrumb] = useState<Breadcrumb>()
  const [detailBreadcrumb, setDetailBreadcrumb] = useState<Breadcrumb>()

  return (
    <BreadcrumbContext.Provider
      value={{
        projectBreadcrumb,
        mainBreadcrumb,
        detailBreadcrumb,
        setProjectBreadcrumb,
        setMainBreadcrumb,
        setDetailBreadcrumb,
      }}
    >
      {children}
    </BreadcrumbContext.Provider>
  )
}
