import { AlertCircleIcon } from 'lucide-react'

interface ErrorStateProps {
  error?: any
}

export const ErrorState = ({ error }: ErrorStateProps) => {
  const title = error?.message ?? 'Unknown error'
  const data = error?.response?.data
  const description = data ? Object.values(data)?.[0] : undefined

  return (
    <div className="flex flex-col items-center py-24">
      <AlertCircleIcon className="w-8 h-8 text-destructive mb-8" />
      <span className="body-large font-medium mb-2">{title}</span>
      {description ? (
        <span className="body-base text-muted-foreground">
          {description as string}
        </span>
      ) : null}
    </div>
  )
}
