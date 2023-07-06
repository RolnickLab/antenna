import { Session } from 'data-services/models/session'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { getRoute } from 'utils/getRoute'
import { STRING, translate } from 'utils/language'
import styles from './session-info.module.scss'

export const SessionInfo = ({ session }: { session: Session }) => {
  const fields = [
    {
      label: translate(STRING.TABLE_COLUMN_DEPLOYMENT),
      value: session.deploymentLabel,
      to: getRoute({ collection: 'deployments', itemId: session.deploymentId }),
    },
    {
      label: translate(STRING.TABLE_COLUMN_DATE),
      value: session.datespanLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_TIME),
      value: session.timespanLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_DURATION),
      value: session.durationLabel,
    },
    {
      label: translate(STRING.TABLE_COLUMN_CAPTURES),
      value: session.numImages,
    },
    {
      label: translate(STRING.TABLE_COLUMN_DETECTIONS),
      value: session.numDetections,
    },
    {
      label: translate(STRING.TABLE_COLUMN_OCCURRENCES),
      value: session.numOccurrences,
      to: getRoute({
        collection: 'occurrences',
        filters: { event: session.id },
      }),
    },
    {
      label: translate(STRING.TABLE_COLUMN_SPECIES),
      value: session.numSpecies,
      to: getRoute({
        collection: 'species',
        filters: { occurrences__event: session.id },
      }),
    },
    {
      label: translate(STRING.TABLE_COLUMN_AVG_TEMP),
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
