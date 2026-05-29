import { Plot } from 'components/plot/lazy-plot'
import { SessionDetails } from 'data-services/models/session-details'

export const SessionPlots = ({ session }: { session: SessionDetails }) => (
  <>
    {session.summaryData.map((summary, index) => {
      if (summary.data.x.length <= 1) {
        return null
      }

      return (
        <Plot
          key={index}
          data={summary.data}
          orientation={summary.orientation}
          title={summary.title}
          type={summary.type}
        />
      )
    })}
  </>
)
