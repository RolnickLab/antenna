import classNames from 'classnames'
import { AlertCircleIcon } from 'lucide-react'
import { useMemo } from 'react'

interface ErrorStateProps {
  compact?: boolean
  error?: any
}

export const ErrorState = ({ compact, error }: ErrorStateProps) => {
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

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <AlertCircleIcon className="w-4 h-4 text-destructive" />
        <span className="pt-0.5 body-small text-muted-foreground">{title}</span>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center py-24">
      <AlertCircleIcon className="w-8 h-8 text-destructive mb-8" />
      <span
        className={classNames('body-large font-medium', {
          'mb-2': description,
        })}
      >
        {title}
      </span>
      {description ? (
        <span className="body-base text-muted-foreground">{description}</span>
      ) : null}
    </div>
  )
}
