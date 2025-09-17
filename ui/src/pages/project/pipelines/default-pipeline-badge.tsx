import classNames from 'classnames'
import { Badge } from 'design-system/components/badge/badge'
import { ChevronRightIcon } from 'lucide-react'
import { buttonVariants, Tooltip } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'

export const DefaultPipelineBadge = ({ projectId }: { projectId: string }) => (
  <Tooltip.Provider delayDuration={0}>
    <Tooltip.Root>
      <Tooltip.Trigger>
        <Badge label="Default" />
      </Tooltip.Trigger>
      <Tooltip.Content side="bottom" className="p-4 max-w-xs">
        <p className="mb-4 whitespace-normal">
          This is the default pipeline used for processing images in this
          project.
        </p>
        <Link
          className={classNames(
            buttonVariants({ size: 'small', variant: 'outline' }),
            '!w-auto'
          )}
          to={APP_ROUTES.PROCESSING({ projectId: projectId })}
        >
          <span>Configure</span>
          <ChevronRightIcon className="w-4 h-4" />
        </Link>
      </Tooltip.Content>
    </Tooltip.Root>
  </Tooltip.Provider>
)
