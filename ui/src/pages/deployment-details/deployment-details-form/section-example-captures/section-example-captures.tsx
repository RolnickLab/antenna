import { DeploymentDetails } from 'data-services/models/deployment-details'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import { InputContent } from 'design-system/components/input/input'
import { ReactNode, useEffect, useState } from 'react'
import styles from './section-example-captures.module.scss'

const IMAGE_CONFIG = {
  MAX_SIZE: 1024 * 1024, // 1MB
  NUM_IMAGES: 12,
  RATIO: 16 / 9,
}

export const SectionExampleCaptures = ({
  deployment,
}: {
  deployment: DeploymentDetails
}) => {
  const [files, setFiles] = useState<File[]>([])

  return (
    <InputContent
      label="Example captures"
      description={`Upload a maximum of ${IMAGE_CONFIG.NUM_IMAGES} images. Valid formats are PNG, GIF and JPEG.`}
    >
      <div className={styles.collection}>
        {deployment.exampleCaptures.map((exampelCapture, index) => (
          <Card key={index}>
            <img src={exampelCapture.src} />
          </Card>
        ))}
        {files.map((file, index) => (
          <Card key={index}>
            <img src={URL.createObjectURL(file)} />
          </Card>
        ))}
        <Card>
          <FileInput
            accept={FileInputAccept.Images}
            label="Choose images"
            multiple
            name="example-captures"
            onChange={(newFiles) => {
              setFiles([...files, ...Array.from(newFiles ?? [])])
            }}
          />
        </Card>
      </div>
    </InputContent>
  )
}

const Card = ({ children }: { children: ReactNode }) => (
  <div
    className={styles.card}
    style={{
      paddingBottom: `${(1 / IMAGE_CONFIG.RATIO) * 100}%`,
    }}
  >
    <div className={styles.cardContent}>{children}</div>
  </div>
)
