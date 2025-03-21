export interface FilterProps {
  data?: any
  error?: string
  onAdd: (value: string) => void
  onClear: () => void
  value: string | undefined
}
