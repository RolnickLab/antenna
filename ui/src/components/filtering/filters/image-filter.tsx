import { FilterProps } from './types'

export const ImageFilter = ({ value }: FilterProps) => {
  const label = (() => {
    if (!value) {
      return 'All images'
    }

    return `#${value}`
  })()

  return (
    <div className="px-2 pt-0.5">
      <span className="text-muted-foreground">{label}</span>
    </div>
  )
}
