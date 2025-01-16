export interface FilterProps {
  error?: string
  onAdd: (value: string) => void
  onClear: () => void
  value: string | undefined
}
