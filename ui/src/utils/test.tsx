/* eslint-disable no-console */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactNode } from 'react'
import { UserContextProvider } from 'utils/user/userContext'

// Local storage mock
export class LocalStorageMock {
  store: { [key: string]: string } = {}

  clear() {
    this.store = {}
  }

  getItem(key: string) {
    return this.store[key] || null
  }

  setItem(key: string, value: string) {
    this.store[key] = String(value)
  }

  removeItem(key: string) {
    delete this.store[key]
  }
}

// App context mock
export const queryClient = new QueryClient({
  logger: {
    log: console.log,
    warn: console.warn,
    error: () => {},
  },
})

export const AppMock = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient as any}>
    <UserContextProvider>{children}</UserContextProvider>
  </QueryClientProvider>
)
