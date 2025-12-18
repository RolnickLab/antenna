import { useRoles } from 'data-services/hooks/team/useRoles'
import { Select } from 'nova-ui-kit'

export const RolesPicker = ({
  value,
  onValueChange,
}: {
  value: string
  onValueChange: (value: string) => void
}) => {
  const { roles = [], isLoading } = useRoles(true)

  return (
    <Select.Root
      disabled={roles.length === 0}
      onValueChange={onValueChange}
      value={value}
    >
      <Select.Trigger loading={isLoading}>
        <Select.Value />
      </Select.Trigger>
      <Select.Content>
        {roles.map((r) => (
          <Select.Item key={r.id} value={r.id}>
            {r.name}
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
