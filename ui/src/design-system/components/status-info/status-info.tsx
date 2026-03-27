import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CircleCheckIcon, CircleQuestionMark, Loader2Icon } from 'lucide-react'
import { Status } from './types'

export const StatusInfo = ({
  status,
  tooltip,
}: {
  status: Status
  tooltip?: string
}) => (
  <BasicTooltip content={tooltip}>
    <StatusIcon status={status} />
  </BasicTooltip>
)

const StatusIcon = ({ status }: { status: Status }) => {
  if (status === Status.Connected) {
    return <CircleCheckIcon className="w-6 h-6 text-success" />
  }

  if (status === Status.NotConnected) {
    return <CircleQuestionMark className="w-6 h-6 text-destructive" />
  }

  return <Loader2Icon className="w-6 h-6 animate-spin text-secondary" />
}
