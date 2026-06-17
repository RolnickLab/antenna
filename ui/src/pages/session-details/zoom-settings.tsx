import { MinusIcon, PlusIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { ReactZoomPanPinchRef } from 'react-zoom-pan-pinch'

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
      <span>Reset</span>
    </Button>
    <Button
      aria-label="Zoom in"
      onClick={() => transformRef.current?.zoomIn()}
      size="icon"
    >
      <PlusIcon className="w-4 h-4" />
    </Button>
    <Button
      aria-label="Zoom out"
      onClick={() => transformRef.current?.zoomOut()}
      size="icon"
    >
      <MinusIcon className="w-4 h-4" />
    </Button>
  </>
)
