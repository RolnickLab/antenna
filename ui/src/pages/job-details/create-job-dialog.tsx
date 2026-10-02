import { FormError } from 'components/form/layout/layout'
import { buildJobPayload } from 'components/form/schema-form/build-job-payload'
import { mapServerErrors } from 'components/form/schema-form/map-server-errors'
import { SchemaField } from 'components/form/schema-form/schema-field'
import {
  FieldDescriptor,
  getInitialValue,
  schemaToFields,
} from 'components/form/schema-form/schema-to-fields'
import { useCreateTypedJob } from 'data-services/hooks/jobs/useCreateTypedJob'
import { useJobTypes } from 'data-services/hooks/jobs/useJobTypes'
import { ServerJobType } from 'data-services/models/job-type'
import { PlusIcon } from 'lucide-react'
import {
  Button,
  Checkbox,
  Dialog,
  Input,
  InputContent,
  LoadingSpinner,
  Select,
} from 'nova-ui-kit'
import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './job-details.module.scss'
import { NewJobDialog } from './new-job-dialog'

const CLOSE_TIMEOUT = 1000

interface FormValues {
  typeKey: string
  variantKey: string
  config: { [field: string]: unknown }
  name: string
  delay: string
  startNow: boolean
}

const getDefaultTypeKey = (jobTypes: ServerJobType[]) =>
  (
    jobTypes.find((t) => t.key === 'ml' && t.allowed) ??
    jobTypes.find((t) => t.allowed)
  )?.key ?? ''

const Divider = ({ label }: { label: string }) => (
  <div className="flex items-center gap-4">
    <span className="pt-0.5 body-small font-semibold text-muted-foreground uppercase">
      {label}
    </span>
    <hr className="flex-1 border-border" />
  </div>
)

const CreateJobForm = ({
  jobTypes,
  projectId,
  onCancel,
  onCreated,
}: {
  jobTypes: ServerJobType[]
  projectId: string
  onCancel: () => void
  onCreated: () => void
}) => {
  const { createJob, isLoading, isSuccess, error } =
    useCreateTypedJob(onCreated)
  const [pickedLabels, setPickedLabels] = useState<{ [field: string]: string }>(
    {}
  )
  const [generalErrors, setGeneralErrors] = useState<string[]>([])
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)

  const { control, handleSubmit, watch, setValue, setError } =
    useForm<FormValues>({
      defaultValues: {
        typeKey: getDefaultTypeKey(jobTypes),
        variantKey: '',
        config: {},
        name: '',
        delay: '0',
        startNow: true,
      },
      mode: 'onChange',
    })

  const typeKey = watch('typeKey')
  // A refetch can drop the selected type (for example a method turned off).
  useEffect(() => {
    if (!jobTypes.some((t) => t.key === typeKey)) {
      setValue('typeKey', getDefaultTypeKey(jobTypes))
      setValue('variantKey', '')
    }
  }, [jobTypes])
  const variantKey = watch('variantKey')
  const jobType = jobTypes.find((t) => t.key === typeKey)
  const variant = jobType?.variants.find((v) => v.key === variantKey)

  const configFields = useMemo(
    () => schemaToFields(variant?.config_schema ?? jobType?.config_schema),
    [jobType, variant]
  )
  const mainFields = configFields.filter((field) => !field.advanced)
  const moreFields = configFields.filter((field) => field.advanced)

  // Settings belong to the selected type and method, so they start
  // fresh (with schema defaults) whenever either changes.
  useEffect(() => {
    const config: { [field: string]: unknown } = {}
    configFields.forEach((field) => {
      config[field.name] = getInitialValue(field)
    })
    setValue('config', config)
    setPickedLabels({})
  }, [typeKey, variantKey])

  useEffect(() => {
    if (!error) {
      setGeneralErrors([])
      return
    }
    const data = (error as any).response?.data
    const { fieldErrors, general } = mapServerErrors(data, {
      configFields: configFields.map((f) => f.name),
    })
    Object.entries(fieldErrors).forEach(([name, message]) =>
      setError(name as any, { message })
    )
    setGeneralErrors(
      general.length || Object.keys(fieldErrors).length
        ? general
        : [(error as Error).message]
    )
  }, [error])

  const onSubmit = async (values: FormValues) => {
    if (!jobType) {
      return
    }
    try {
      await createJob(
        buildJobPayload({
          projectId,
          jobType,
          variant,
          pickedLabels,
          configValues: values.config,
          name: values.name,
          delay: values.delay,
          startNow: values.startNow,
        })
      )
    } catch {
      // Shown through the `error` state above.
    }
  }

  const renderField = (field: FieldDescriptor) => (
    <SchemaField
      key={`${typeKey}-${variantKey}-${field.name}`}
      control={control}
      field={field}
      formName={`config.${field.name}`}
      projectId={projectId}
      onLabelChange={(label) =>
        setPickedLabels((labels) => ({ ...labels, [field.name]: label ?? '' }))
      }
    />
  )

  const variantReady = !jobType?.variant_key || !!variant

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="flex flex-col gap-6 px-8 py-6"
    >
      {generalErrors.length ? (
        <FormError
          inDialog
          intro={translate(STRING.MESSAGE_COULD_NOT_SAVE)}
          message={generalErrors.join(' ')}
        />
      ) : null}
      <InputContent
        label={translate(STRING.JOB_FIELD_TYPE)}
        description={jobType?.description}
      >
        <Select.Root
          value={typeKey}
          onValueChange={(value) => {
            setValue('typeKey', value)
            setValue('variantKey', '')
          }}
        >
          <Select.Trigger aria-label={translate(STRING.JOB_FIELD_TYPE)}>
            <Select.Value />
          </Select.Trigger>
          <Select.Content>
            {jobTypes.map((t) => (
              <Select.Item key={t.key} value={t.key} disabled={!t.allowed}>
                {t.allowed
                  ? t.name
                  : `${t.name} (${translate(STRING.JOB_NOT_PERMITTED)})`}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </InputContent>
      {jobType?.variant_key ? (
        <InputContent
          label={translate(STRING.JOB_FIELD_METHOD)}
          description={variant?.description}
        >
          <Select.Root
            value={variantKey}
            onValueChange={(value) => setValue('variantKey', value)}
          >
            <Select.Trigger aria-label={translate(STRING.JOB_FIELD_METHOD)}>
              <Select.Value
                placeholder={translate(STRING.SELECT_PLACEHOLDER)}
              />
            </Select.Trigger>
            <Select.Content>
              {jobType.variants.map((v) => (
                <Select.Item key={v.key} value={v.key}>
                  {v.name}
                </Select.Item>
              ))}
            </Select.Content>
          </Select.Root>
        </InputContent>
      ) : null}
      {variantReady ? (
        <>
          {configFields.length ? (
            <>
              {variant ? (
                <Divider
                  label={translate(STRING.JOB_SETTINGS_DIVIDER, {
                    method: variant.name,
                  })}
                />
              ) : null}
              {mainFields.map((field) => renderField(field))}
              {moreFields.length ? (
                <div className="flex flex-col gap-6">
                  <button
                    type="button"
                    className="text-left body-small font-semibold text-primary"
                    onClick={() => setMoreOpen((open) => !open)}
                    aria-expanded={moreOpen}
                  >
                    {translate(STRING.JOB_MORE_SETTINGS)} {moreOpen ? '▾' : '▸'}
                  </button>
                  {moreOpen
                    ? moreFields.map((field) => renderField(field))
                    : null}
                </div>
              ) : null}
            </>
          ) : null}
        </>
      ) : null}
      <div className="flex flex-col gap-4">
        <button
          type="button"
          className="text-left body-small font-semibold text-primary"
          onClick={() => setAdvancedOpen((open) => !open)}
          aria-expanded={advancedOpen}
        >
          {translate(STRING.JOB_ADVANCED)} {advancedOpen ? '▾' : '▸'}
        </button>
        {advancedOpen ? (
          <div className="grid grid-cols-2 gap-4">
            <Input
              {...control.register('name')}
              label={translate(STRING.FIELD_LABEL_NAME)}
              value={watch('name')}
            />
            <Input
              {...control.register('delay')}
              label={translate(STRING.FIELD_LABEL_DELAY)}
              type="number"
              value={watch('delay')}
            />
          </div>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-4">
        <Checkbox
          checked={watch('startNow')}
          id="start-now"
          label={translate(STRING.JOB_START_IMMEDIATELY)}
          onCheckedChange={(checked) => setValue('startNow', checked)}
        />
        <div className="flex items-center gap-2">
          <Button size="small" variant="ghost" type="button" onClick={onCancel}>
            {translate(STRING.CANCEL)}
          </Button>
          <Button
            size="small"
            variant="success"
            type="submit"
            disabled={isLoading || isSuccess || !jobType || !variantReady}
          >
            {watch('startNow')
              ? translate(STRING.JOB_START_NOW)
              : translate(STRING.JOB_CREATE)}
          </Button>
        </div>
      </div>
    </form>
  )
}

export const CreateJobDialog = () => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { jobTypes, isLoading, error } = useJobTypes(projectId)

  // The previous dialog stays reachable if the job types request fails.
  if (error) {
    return <NewJobDialog />
  }

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>{translate(STRING.JOB_CREATE)}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={translate(STRING.JOB_CREATE)} />
        <div className={styles.content}>
          {isLoading || !jobTypes ? (
            <LoadingSpinner />
          ) : (
            <CreateJobForm
              jobTypes={jobTypes}
              projectId={projectId as string}
              onCancel={() => setIsOpen(false)}
              onCreated={() =>
                setTimeout(() => setIsOpen(false), CLOSE_TIMEOUT)
              }
            />
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
