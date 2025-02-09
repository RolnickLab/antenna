import { AlertCircleIcon } from 'lucide-react'
import { useMemo } from 'react'

interface ErrorStateProps {
  error?: any
}

export const ErrorState = ({ error }: ErrorStateProps) => {
  const title = error?.message ?? 'Unknown error'
  const data = error?.response?.data

  const description = useMemo(() => {
    const entries =
      data && typeof data === 'object' ? Object.entries(data) : undefined

    if (entries?.length) {
      const [key, value] = entries[0]

      return `${key}: ${value}`
    }
  }, [error])

  return (
    <div className="flex flex-col items-center py-24">
      <AlertCircleIcon className="w-8 h-8 text-destructive mb-8" />
      <span className="body-large font-medium mb-2">{title}</span>
      {description ? (
        <span className="body-base text-muted-foreground">{description}</span>
      ) : null}
    </div>
  )
}
