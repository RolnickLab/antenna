import { Badge } from 'design-system/components/badge/badge'
import { Info } from 'design-system/components/info-tooltip'
import { Tooltip } from 'nova-ui-kit'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'

export const DefaultPipelineBadge = ({ projectId }: { projectId: string }) => (
  <Tooltip.Provider delayDuration={0}>
    <Tooltip.Root>
      <Tooltip.Trigger>
        <Badge label={translate(STRING.DEFAULT)} />
      </Tooltip.Trigger>
      <Tooltip.Content side="bottom" className="p-4 max-w-xs">
        <Info
          text={translate(STRING.MESSAGE_DEFAULT_PIPELINE)}
          link={{
            text: translate(STRING.CONFIGURE),
            to: APP_ROUTES.PROCESSING({ projectId: projectId }),
          }}
        />
      </Tooltip.Content>
    </Tooltip.Root>
  </Tooltip.Provider>
)
