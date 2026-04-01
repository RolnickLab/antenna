import classNames from 'classnames'
import { useGenerateAPIKey } from 'data-services/hooks/processing-services/useGenerateAPIKey'
import { usePopulateProcessingService } from 'data-services/hooks/processing-services/usePopulateProcessingService'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, Eye, EyeOff, KeyRound, Loader2 } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const PopulateProcessingService = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const { populateProcessingService, isLoading, error } =
    usePopulateProcessingService()

  return (
    <BasicTooltip
      asChild
      content={
        error
          ? 'Could not register the pipelines, please check the endpoint URL.'
          : undefined
      }
    >
      <Button
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => populateProcessingService(processingService.id)}
        size="small"
        variant="outline"
      >
        {error ? <AlertCircleIcon className="w-4 h-4" /> : null}
        <span>{translate(STRING.REGISTER_PIPELINES)}</span>
        {isLoading ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : null}
      </Button>
    </BasicTooltip>
  )
}

export const GenerateAPIKey = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const { projectId } = useParams()
  const { generateAPIKey, isLoading, error, apiKey } = useGenerateAPIKey(projectId)
  const [copied, setCopied] = useState(false)
  const [visible, setVisible] = useState(false)

  const handleCopy = async () => {
    if (apiKey) {
      await navigator.clipboard.writeText(apiKey)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (apiKey) {
    return (
      <div className="flex flex-col gap-2 p-3 border rounded-md bg-muted/50">
        <p className="text-sm font-medium">
          API Key (shown once, copy it now):
        </p>
        <div className="flex items-center gap-2">
          <code className="text-xs bg-background px-2 py-1 rounded border break-all flex-1 font-mono">
            {visible ? apiKey : '\u2022'.repeat(20)}
          </code>
          <Button
            aria-label={visible ? 'Hide API key' : 'Show API key'}
            onClick={() => setVisible((v) => !v)}
            size="small"
            variant="ghost"
          >
            {visible ? (
              <EyeOff className="w-4 h-4" />
            ) : (
              <Eye className="w-4 h-4" />
            )}
          </Button>
          <Button onClick={handleCopy} size="small" variant="outline">
            {copied ? 'Copied' : 'Copy'}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <BasicTooltip
      asChild
      content={
        error
          ? 'Could not generate API key.'
          : processingService.apiKeyPrefix
          ? `Current key prefix: ${processingService.apiKeyPrefix}. Generating a new key will revoke the current one.`
          : 'Generate an API key for this service to authenticate with.'
      }
    >
      <Button
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => generateAPIKey(processingService.id)}
        size="small"
        variant="outline"
      >
        {error ? <AlertCircleIcon className="w-4 h-4" /> : null}
        <KeyRound className="w-4 h-4" />
        <span>
          {processingService.apiKeyPrefix
            ? 'Regenerate API Key'
            : 'Generate API Key'}
        </span>
        {isLoading ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : null}
      </Button>
    </BasicTooltip>
  )
}
