import { Project } from 'data-services/models/project'
import { Button } from 'design-system/components/button/button'
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
        name="project-image"
        renderInput={(props) => (
          <Button
            {...props}
            label={imageUrl ? 'Change image' : 'Choose image'}
          />
        )}
        withClear
        onChange={(files) => onChange(files ? files[0] : null)}
      />
    </>
  )
}
