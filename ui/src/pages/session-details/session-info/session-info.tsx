import { Session } from 'data-services/models/session'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { useParams } from 'react-router-dom'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './session-info.module.scss'

export const SessionInfo = ({ session }: { session: Session }) => {
  const { projectId } = useParams()

  const fields = [
    {
      label: translate(STRING.FIELD_LABEL_DEPLOYMENT),
      value: session.deploymentLabel,
      to: getAppRoute({
        projectId: projectId as string,
        collection: 'deployments',
        itemId: session.deploymentId,
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_DATE),
      value: session.datespanLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_TIME),
      value: session.timespanLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_DURATION),
      value: session.durationLabel,
    },
    {
      label: translate(STRING.FIELD_LABEL_CAPTURES),
      value: session.numImages,
    },
    {
      label: translate(STRING.FIELD_LABEL_DETECTIONS),
      value: session.numDetections,
    },
    {
      label: translate(STRING.FIELD_LABEL_OCCURRENCES),
      value: session.numOccurrences,
      to: getAppRoute({
        projectId: projectId as string,
        collection: 'occurrences',
        filters: { event: session.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_SPECIES),
      value: session.numSpecies,
      to: getAppRoute({
        projectId: projectId as string,
        collection: 'species',
        filters: { occurrences__event: session.id },
      }),
    },
    {
      label: translate(STRING.FIELD_LABEL_AVG_TEMP),
      value: session.tempLabel,
    },
  ]

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>{session.label}</h1>
      <div className={styles.content}>
        <InfoBlock fields={fields} />
      </div>
    </div>
  )
}
