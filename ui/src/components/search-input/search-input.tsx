import { SearchIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useDebounce } from 'utils/useDebounce'

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
  const debouncedSearchString = useDebounce(searchString, DEBOUNCE_DELAY)

  useEffect(() => {
    if (debouncedSearchString.trim() !== value) {
      onChange(debouncedSearchString.trim())
    }
  }, [debouncedSearchString])

  return (
    <div className="flex items-center h-8 w-56 gap-2 px-4 rounded-full border border-input bg-background focus-within:ring-2 focus-within:ring-ring">
      <SearchIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
      <input
        aria-label={label}
        className="w-full bg-transparent body-small outline-none placeholder:text-muted-foreground"
        placeholder={label}
        type="search"
        value={searchString}
        onChange={(e) => setSearchString(e.target.value)}
      />
    </div>
  )
}
