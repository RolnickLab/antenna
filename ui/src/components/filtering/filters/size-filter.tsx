import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { FilterProps } from './types'

const toDisplay = (value: string | undefined, isRelative: boolean) => {
  if (!value) {
    return ''
  }
  return isRelative ? `${Number((Number(value) * 100).toFixed(4))}` : value
}

// Relative sizes are stored as a fraction of the capture but entered as a percentage.
const SizeFilter = ({
  error,
  isRelative,
  onAdd,
  onClear,
  value,
}: FilterProps & { isRelative: boolean }) => {
  const unit = isRelative ? '%' : 'mm'
  const [draft, setDraft] = useState(toDisplay(value, isRelative))

  useEffect(() => {
    setDraft(toDisplay(value, isRelative))
  }, [value, isRelative])

  const commit = () => {
    if (!draft.trim().length) {
      onClear()
      return
    }
    const number = Number(draft)
    onAdd(isRelative ? `${number / 100}` : draft)
  }

  return (
    <div className="flex w-full items-center gap-2">
      <input
        aria-invalid={!!error}
        aria-label={`${translate(STRING.FIELD_LABEL_SIZE)} (${unit})`}
        className="h-8 w-full rounded-md border border-border bg-background px-3 body-small"
        inputMode="decimal"
        min={0}
        onBlur={commit}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            commit()
          }
        }}
        step="any"
        type="number"
        value={draft}
      />
      <span className="body-small text-muted-foreground">
        {unit}
      </span>
    </div>
  )
}

export const MmSizeFilter = (props: FilterProps) => (
  <SizeFilter {...props} isRelative={false} />
)

export const RelativeSizeFilter = (props: FilterProps) => (
  <SizeFilter {...props} isRelative />
)
