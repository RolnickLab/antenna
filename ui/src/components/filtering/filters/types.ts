export interface FilterProps {
  isValid?: boolean
  onAdd: (value: string) => void
  onClear: () => void
  value: string | undefined
}
