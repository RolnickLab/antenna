import classNames from 'classnames'
import { ChevronRightIcon, InfoIcon } from 'lucide-react'
import { Button, buttonVariants, Tooltip } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const InfoTooltip = (props: {
  text: string
  link?: {
    text: string
    to: string
  }
}) => (
  <Tooltip.Provider delayDuration={0}>
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Button aria-label={translate(STRING.INFO)} size="icon" variant="ghost">
          <InfoIcon className="w-4 h-4" />
        </Button>
      </Tooltip.Trigger>
      <Tooltip.Content side="bottom" className="p-4 max-w-xs">
        <Info {...props} />
      </Tooltip.Content>
    </Tooltip.Root>
  </Tooltip.Provider>
)

export const Info = ({
  link,
  text,
}: {
  text: string
  link?: {
    text: string
    to: string
  }
}) => (
  <div className="flex flex-col gap-4">
    <p className="body-small whitespace-normal">{text}</p>
    {link ? (
      <Link
        className={classNames(
          buttonVariants({ size: 'small', variant: 'ghost' }),
          '!w-auto self-end'
        )}
        to={link.to}
      >
        <span>{link.text}</span>
        <ChevronRightIcon className="w-4 h-4" />
      </Link>
    ) : null}
  </div>
)
