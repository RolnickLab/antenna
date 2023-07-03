import { Session } from 'data-services/models/session'
import { InfoBlock } from 'design-system/components/info-block/info-block'
import { STRING, translate } from 'utils/language'
import styles from './session-info.module.scss'

export const SessionInfo = ({ session }: { session: Session }) => {
  const fields = [
    {
      label: translate(STRING.DETAILS_LABEL_DEPLOYMENT),
      value: session.deploymentLabel,
      to: `/deployments/${session.deploymentId}`,
    },
    {
      label: translate(STRING.DETAILS_LABEL_DATE),
      value: session.datespanLabel,
    },
    {
      label: translate(STRING.DETAILS_LABEL_TIME),
      value: session.timespanLabel,
    },
    {
      label: translate(STRING.DETAILS_LABEL_DURATION),
      value: session.durationLabel,
    },
  ]

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>
        {translate(STRING.SESSION)} {session.idLabel}
      </h1>
      <div className={styles.content}>
        <div className={styles.fields}>
          <InfoBlock fields={fields} />
        </div>
      </div>
    </div>
  )
}
