import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import { Capture } from 'data-services/models/capture'
import { JobStatus } from 'data-services/models/job'
import { SessionDetails } from 'data-services/models/session-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { JobDetails } from 'pages/job-details/job-details'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useThreshold } from 'utils/threshold/thresholdContext'
import styles from './playback-controls.module.scss'

export const PlaybackControls = ({
  activeCapture,
  session,
}: {
  activeCapture?: Capture
  session: SessionDetails
}) => {
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <div className={styles.controls}>
      {activeCapture && (
        <CaptureJob key={activeCapture.id} activeCapture={activeCapture} />
      )}
      <div className={styles.slider}>
        {session.numDetections && session.numDetections > 0 ? (
          <PlaybackSlider
            defaultValue={defaultThreshold}
            label="Score"
            value={displayThreshold}
            onValueChange={setDisplayThreshold}
            onValueCommit={(value) => {
              setDisplayThreshold(value)
              setThreshold(value)
            }}
          />
        ) : null}
      </div>
    </div>
  )
}

const CaptureJob = ({ activeCapture }: { activeCapture: Capture }) => {
  const [jobId, setJobId] = useState<string>()
  const { projectId } = useParams()
  const { createJob, isLoading, isSuccess } = useCreateJob(setJobId)

  return (
    <>
      <Button
        label="Process capture"
        loading={isLoading}
        theme={ButtonTheme.Neutral}
        icon={isSuccess ? IconType.RadixCheck : IconType.BatchId}
        onClick={() => {
          if (isSuccess) {
            return
          }
          createJob({
            name: `Capture #${activeCapture.id}`,
            projectId: projectId as string,
            status: JobStatus.Pending,
          })
        }}
      />
      {jobId && <JobDetailsDialog id={jobId} />}
    </>
  )
}

export const JobDetailsDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { job, isLoading, isFetching } = useJobDetails(id)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton theme={IconButtonTheme.Neutral} icon={IconType.BatchId} />
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {job ? (
          <JobDetails job={job} title="Job details" isFetching={isFetching} />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
