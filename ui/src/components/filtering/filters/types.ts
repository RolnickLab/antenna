export interface FilterProps {
  value: string | undefined
  onAdd: (value: string) => void
  onClear: () => void
}
