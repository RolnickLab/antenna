import { ReactNode } from 'react'

export const Toolbar = ({ children }: { children: ReactNode }) => (
  <div className="flex items-center justify-end px-4">
    <div className="w-min flex items-center justify-center gap-1 p-1 bg-background rounded-full hover-device:shadow-toolbar">
      {children}
    </div>
  </div>
)
