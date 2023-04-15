/* eslint-disable @typescript-eslint/no-empty-function */

import { createContext, ReactNode, useState } from 'react'

export interface Breadcrumb {
  title: string
  path: string
}

interface BreadcrumbContextValues {
  mainBreadcrumb?: Breadcrumb
  detailBreadcrumb?: Breadcrumb
  setMainBreadcrumb: (breadcrumb?: Breadcrumb) => void
  setDetailBreadcrumb: (breadcrumb?: Breadcrumb) => void
}

export const BreadcrumbContext = createContext<BreadcrumbContextValues>({
  mainBreadcrumb: undefined,
  detailBreadcrumb: undefined,
  setMainBreadcrumb: () => {},
  setDetailBreadcrumb: () => {},
})

export const BreadcrumbContextProvider = ({
  children,
}: {
  children: ReactNode
}) => {
  const [mainBreadcrumb, setMainBreadcrumb] = useState<Breadcrumb>()
  const [detailBreadcrumb, setDetailBreadcrumb] = useState<Breadcrumb>()

  return (
    <BreadcrumbContext.Provider
      value={{
        mainBreadcrumb,
        detailBreadcrumb,
        setMainBreadcrumb,
        setDetailBreadcrumb,
      }}
    >
      {children}
    </BreadcrumbContext.Provider>
  )
}
