import { BasicTooltip } from 'design-system'
import { CircleCheckIcon, CircleQuestionMark, Loader2Icon } from 'lucide-react'
import { ConnectionStatus } from './types'

export const ConnectionStatusInfo = ({
  status,
  tooltip,
}: {
  status: ConnectionStatus
  tooltip?: string
}) => (
  <BasicTooltip content={tooltip}>
    <StatusIcon status={status} />
  </BasicTooltip>
)

const StatusIcon = ({ status }: { status: ConnectionStatus }) => {
  if (status === ConnectionStatus.Connected) {
    return <CircleCheckIcon className="w-6 h-6 text-success" />
  }

  if (status === ConnectionStatus.NotConnected) {
    return <CircleQuestionMark className="w-6 h-6 text-destructive" />
  }

  return <Loader2Icon className="w-6 h-6 animate-spin text-secondary" />
}
