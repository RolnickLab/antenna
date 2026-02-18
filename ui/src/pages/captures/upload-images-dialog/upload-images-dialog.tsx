import classNames from 'classnames'
import {
  FormActions,
  FormError,
  FormSection,
} from 'components/form/layout/layout'
import { useUploadCaptures } from 'data-services/hooks/captures/useUploadCaptures'
import { useDeployments } from 'data-services/hooks/deployments/useDeployments'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { Deployment } from 'data-services/models/deployment'
import { ProjectDetails } from 'data-services/models/project-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { FormStepper } from 'design-system/components/form-stepper/form-stepper'
import { InputValue } from 'design-system/components/input/input'
import {
  ChevronRight,
  ChevronRightIcon,
  InfoIcon,
  Loader2Icon,
  UploadIcon,
} from 'lucide-react'
import { Button, buttonVariants, Select, Switch, Tooltip } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { SelectImagesSection } from './select-images-section/select-images-section'
import styles from './styles.module.scss'

enum Section {
  Images = 'images',
  Station = 'station',
  Upload = 'upload',
}

export const UploadImagesDialog = ({
  buttonSize = 'small',
  buttonVariant = 'outline',
  isOpen,
  setIsOpen,
}: {
  buttonSize?: string
  buttonVariant?: string
  isOpen: boolean
  setIsOpen: (isOpen: boolean) => void
}) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const [currentSection, setCurrentSection] = useState<string>(Section.Images)
  const [deployment, setDeployment] = useState<Deployment>()
  const [images, setImages] = useState<{ file: File }[]>([])
  const [processNow, setProcessNow] = useState(
    !!project?.settings.defaultProcessingPipeline
  )

  const { uploadCaptures, isLoading, isSuccess, error } = useUploadCaptures()

  useEffect(() => {
    setCurrentSection(Section.Images)
    setImages([])
    setDeployment(undefined)
  }, [isOpen])

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size={buttonSize} variant={buttonVariant}>
          <UploadIcon className="w-4 h-4" />
          <span>Upload images</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title="Upload images"></Dialog.Header>
        {error ? <FormError message={error} /> : null}
        <div className={styles.content}>
          {isSuccess ? (
            <div className="flex flex-col items-center pt-32">
              <h1 className="mb-8 heading-large">Upload complete</h1>
              {processNow ? (
                <>
                  <p className="text-center body-large mb-16">
                    Stay tuned while your images are being processed.
                  </p>
                  <Link
                    className={buttonVariants({ variant: 'success' })}
                    to={APP_ROUTES.JOBS({ projectId: projectId as string })}
                  >
                    <span>View job details</span>
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </>
              ) : (
                <>
                  <p className="text-center body-large mb-16">
                    Your images were uploaded and added to the selected
                    monitoring station.
                  </p>
                  <Link
                    className={buttonVariants({ variant: 'success' })}
                    onClick={() => setIsOpen(false)}
                    to={APP_ROUTES.CAPTURES({ projectId: projectId as string })}
                  >
                    <span>View captures</span>
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </>
              )}
            </div>
          ) : (
            <>
              <div className={styles.section}>
                <FormStepper
                  items={[
                    {
                      id: Section.Images,
                      label: 'Select images',
                    },
                    {
                      id: Section.Station,
                      label: 'Select station',
                    },
                    {
                      id: Section.Upload,
                      label: 'Upload',
                    },
                  ]}
                  currentItemId={currentSection}
                  setCurrentItemId={setCurrentSection}
                />
              </div>
              {currentSection === Section.Images ? (
                <SectionImages
                  images={images}
                  setCurrentSection={setCurrentSection}
                  setImages={setImages}
                />
              ) : null}
              {currentSection === Section.Station ? (
                <SectionStation
                  deployment={deployment}
                  setDeployment={setDeployment}
                  setCurrentSection={setCurrentSection}
                />
              ) : null}
              {currentSection === Section.Upload ? (
                <SectionUpload
                  deployment={deployment}
                  images={images}
                  isLoading={isLoading}
                  onSubmit={() => {
                    if (deployment && images.length) {
                      uploadCaptures({
                        projectId: projectId as string,
                        deploymentId: deployment?.id,
                        files: images.map(({ file }) => file),
                        processNow,
                      })
                    }
                  }}
                  processNow={processNow}
                  project={project as ProjectDetails}
                  setCurrentSection={setCurrentSection}
                  setProcessNow={setProcessNow}
                />
              ) : null}
            </>
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}

const SectionImages = ({
  images,
  setCurrentSection,
  setImages,
}: {
  images: { file: File }[]
  setCurrentSection: (section: Section) => void
  setImages: (images: { file: File }[]) => void
}) => (
  <div>
    <SelectImagesSection images={images} setImages={setImages} />
    <div className="grow" />
    <FormActions>
      <Button
        onClick={() => setCurrentSection(Section.Station)}
        size="small"
        variant="outline"
      >
        <span>{translate(STRING.NEXT)}</span>
      </Button>
    </FormActions>
  </div>
)

const SectionStation = ({
  deployment,
  setCurrentSection,
  setDeployment,
}: {
  deployment?: Deployment
  setCurrentSection: (section: Section) => void
  setDeployment: (deployment?: Deployment) => void
}) => {
  const { projectId } = useParams()
  const { deployments = [], isLoading } = useDeployments({
    projectId: projectId as string,
  })

  useEffect(() => {
    // Pre select first deployment
    if (deployments.length) {
      setDeployment(deployments[0])
    }
  }, [deployments])

  return (
    <div>
      <FormSection
        title="Select station"
        description="The images will be added to one of your monitoring stations."
      >
        <Select.Root
          disabled={deployments.length === 0}
          value={deployment?.id}
          onValueChange={(value) =>
            setDeployment(
              deployments.find((deployment) => deployment.id === value)
            )
          }
        >
          <Select.Trigger loading={isLoading}>
            <Select.Value placeholder="Select a value" />
          </Select.Trigger>
          <Select.Content className="max-h-72">
            {deployments.map((d) => (
              <Select.Item key={d.id} value={d.id}>
                {d.name}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      </FormSection>
      <FormActions>
        <Button
          onClick={() => setCurrentSection(Section.Images)}
          size="small"
          variant="outline"
        >
          <span>{translate(STRING.BACK)}</span>
        </Button>
        <Button
          onClick={() => setCurrentSection(Section.Upload)}
          size="small"
          variant="outline"
        >
          <span>{translate(STRING.NEXT)}</span>
        </Button>
      </FormActions>
    </div>
  )
}

const SectionUpload = ({
  deployment,
  images,
  isLoading,
  onSubmit,
  processNow,
  project,
  setCurrentSection,
  setProcessNow,
}: {
  deployment?: Deployment
  images: { file: File }[]
  isLoading: boolean
  onSubmit: () => void
  processNow: boolean
  project: ProjectDetails
  setCurrentSection: (section: Section) => void
  setProcessNow: (processingEnabled: boolean) => void
}) => (
  <div>
    <FormSection
      title="Summary"
      description="Your images will be uploaded and added to the selected monitoring station. If processing is enabled, a job will start in the background."
    >
      <div className="grid grid-cols-2 gap-8">
        <InputValue label="Images" value={images.length} />
        <InputValue label="Station" value={deployment?.name} />
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Switch
              checked={processNow}
              disabled={!project.settings.defaultProcessingPipeline}
              onCheckedChange={setProcessNow}
            />
            <label className="pt-0.5 body-small text-muted-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-50">
              Process images
            </label>
            <DefaultPipelineInfo project={project} />
          </div>
        </div>
      </div>
    </FormSection>
    <FormActions>
      <Button
        onClick={() => setCurrentSection(Section.Images)}
        size="small"
        variant="outline"
      >
        <span>{translate(STRING.BACK)}</span>
      </Button>
      <Button
        disabled={!(deployment && images.length)}
        onClick={onSubmit}
        size="small"
        variant="success"
      >
        <span>Upload</span>
        {isLoading ? (
          <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
        ) : null}
      </Button>
    </FormActions>
  </div>
)

const DefaultPipelineInfo = ({ project }: { project: ProjectDetails }) => (
  <Tooltip.Provider delayDuration={0}>
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <Button size="icon" variant="ghost">
          <InfoIcon className="w-4 h-4" />
        </Button>
      </Tooltip.Trigger>
      <Tooltip.Content side="bottom" className="p-4 space-y-4 max-w-xs">
        {project.settings.defaultProcessingPipeline ? (
          <InputValue
            label="Default processing pipeline"
            value={project.settings.defaultProcessingPipeline?.name}
          />
        ) : (
          <p className="whitespace-normal">
            The project has no default processing pipeline configured.
          </p>
        )}
        <Link
          className={classNames(
            buttonVariants({ size: 'small', variant: 'outline' }),
            '!w-auto'
          )}
          to={APP_ROUTES.PROCESSING({ projectId: project.id })}
        >
          <span>Configure</span>
          <ChevronRightIcon className="w-4 h-4" />
        </Link>
      </Tooltip.Content>
    </Tooltip.Root>
  </Tooltip.Provider>
)
