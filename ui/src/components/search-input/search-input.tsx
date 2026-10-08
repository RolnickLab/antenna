import { SearchIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const DEBOUNCE_DELAY = 300

export const SearchInput = ({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) => {
  const [searchString, setSearchString] = useState(value)
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>()

  // Follow the value when it changes from outside the box, for example on
  // browser Back, and drop any pending change so it cannot restore the old term.
  // A value that only differs by surrounding spaces is the box's own update.
  useEffect(() => {
    clearTimeout(timeoutRef.current)
    setSearchString((current) => (current.trim() === value ? current : value))
  }, [value])

  useEffect(() => () => clearTimeout(timeoutRef.current), [])

  const onInputChange = (newSearchString: string) => {
    setSearchString(newSearchString)
    clearTimeout(timeoutRef.current)
    timeoutRef.current = setTimeout(() => {
      if (newSearchString.trim() !== value) {
        onChange(newSearchString.trim())
      }
    }, DEBOUNCE_DELAY)
  }

  return (
    <div className="flex items-center h-8 w-56 gap-2 px-4 rounded-full border border-input bg-background focus-within:ring-2 focus-within:ring-ring">
      <SearchIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
      <input
        aria-label={label}
        className="w-full h-full pt-0.5 bg-transparent body-small outline-none placeholder:text-muted-foreground"
        placeholder={label}
        type="search"
        value={searchString}
        onChange={(e) => onInputChange(e.target.value)}
      />
    </div>
  )
}
