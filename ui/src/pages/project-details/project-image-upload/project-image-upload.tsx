import { Project } from 'data-services/models/project'
import { FileInput } from 'design-system/components/file-input/file-input'
import { FileInputAccept } from 'design-system/components/file-input/types'
import styles from './project-image-upload.module.scss'

export const ProjectImageUpload = ({
  file,
  project,
  onChange,
}: {
  file?: File | null
  project: Project
  onChange: (file: File | null) => void
}) => {
  const imageUrl = (() => {
    if (file) {
      return URL.createObjectURL(file)
    }
    if (file === null) {
      return undefined
    }
    return project.image
  })()

  return (
    <>
      <div className={styles.container}>
        {imageUrl ? (
          <img src={imageUrl} />
        ) : (
          <span className={styles.info}>No image</span>
        )}
      </div>
      <FileInput
        accept={FileInputAccept.Images}
        label={imageUrl ? 'Change image' : 'Choose image'}
        name="image"
        onChange={onChange}
      />
    </>
  )
}
