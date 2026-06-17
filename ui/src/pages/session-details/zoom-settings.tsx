import { MinusIcon, PlusIcon } from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { ReactZoomPanPinchRef } from 'react-zoom-pan-pinch'
import { STRING, translate } from 'utils/language'

export const ZoomSettings = ({
  transformRef,
}: {
  transformRef: React.RefObject<ReactZoomPanPinchRef>
}) => (
  <>
    <Button
      onClick={() => transformRef.current?.resetTransform()}
      size="small"
      variant="ghost"
    >
      <span>{translate(STRING.RESET)}</span>
    </Button>

    <BasicTooltip content={translate(STRING.ZOOM_IN)}>
      <Button
        aria-label={translate(STRING.ZOOM_IN)}
        onClick={() => transformRef.current?.zoomIn()}
        size="icon"
      >
        <PlusIcon className="w-4 h-4" />
      </Button>
    </BasicTooltip>
    <BasicTooltip content={translate(STRING.ZOOM_OUT)}>
      <Button
        aria-label={translate(STRING.ZOOM_OUT)}
        onClick={() => transformRef.current?.zoomOut()}
        size="icon"
      >
        <MinusIcon className="w-4 h-4" />
      </Button>
    </BasicTooltip>
  </>
)
