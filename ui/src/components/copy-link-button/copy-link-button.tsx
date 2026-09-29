import { SUCCESS_TIMEOUT } from 'data-services/constants'
import { CheckIcon, LinkIcon } from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'

// Callers pass the text to put on the clipboard, usually a shareable page URL.
export const CopyLinkButton = ({ value }: { value: string }) => {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) {
      return
    }

    const timeout = setTimeout(() => setCopied(false), SUCCESS_TIMEOUT)

    return () => clearTimeout(timeout)
  }, [copied])

  const label = copied ? translate(STRING.COPIED) : translate(STRING.COPY_LINK)

  return (
    <BasicTooltip asChild content={label}>
      <Button
        aria-label={label}
        onClick={() =>
          navigator.clipboard.writeText(value).then(() => setCopied(true))
        }
        size="icon"
        variant="ghost"
      >
        {copied ? (
          <CheckIcon className="w-4 h-4" />
        ) : (
          <LinkIcon className="w-4 h-4" />
        )}
      </Button>
    </BasicTooltip>
  )
}
