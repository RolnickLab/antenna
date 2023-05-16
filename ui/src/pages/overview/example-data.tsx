import { MarkerPosition } from 'design-system/map/multiple-marker-map'
import { STRING, translate } from 'utils/language'

export const EXAMPLE_DATA = {
  y: [18, 45, 98, 120, 109, 113, 43],
  x: ['8PM', '9PM', '10PM', '11PM', '12PM', '13PM', '14PM'],
  tickvals: ['8PM', '', '', '', '', '', '14PM'],
}

export const EXAMPLE_POPUP_CONTENT = (
  <>
    <p>
      <a href="/deployments/vermont-luna-sample">
        <span>vermont-luna-sample</span>
      </a>
    </p>
    <p>
      <span>{translate(STRING.DETAILS_LABEL_SESSIONS)}: 1</span>
      <br />
      <span>{translate(STRING.DETAILS_LABEL_IMAGES)}: 18</span>
      <br />
      <span>{translate(STRING.DETAILS_LABEL_DETECTIONS)}: 24</span>
    </p>
  </>
)

export const EXAMPLE_MARKERS = [
  {
    position: new MarkerPosition(52.30767, 5.04011),
    popupContent: EXAMPLE_POPUP_CONTENT,
  },
  {
    position: new MarkerPosition(52.31767, 5.06011),
    popupContent: EXAMPLE_POPUP_CONTENT,
  },
  {
    position: new MarkerPosition(52.32767, 5.09011),
    popupContent: EXAMPLE_POPUP_CONTENT,
  },
]
