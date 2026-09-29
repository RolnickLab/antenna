import { OccurrenceFrame, ServerOccurrenceFrame } from './occurrence-details'

export interface ServerOccurrenceFramesPage {
  count: number
  next: string | null
  previous: string | null
  results: ServerOccurrenceFrame[]
}

/** A page by position, or the page holding one detection. */
export type FramePageRequest = { offset: number } | { around: string }

export const FIRST_FRAME_PAGE: FramePageRequest = { offset: 0 }

export const isFirstFramePage = (request: FramePageRequest) =>
  'offset' in request && request.offset === 0

export const getFramePageQuery = (request: FramePageRequest) =>
  'around' in request
    ? `around=${encodeURIComponent(request.around)}`
    : `offset=${request.offset}`

/** The page a `next` or `previous` link points at; offset 0 when the link omits it. */
export const getLinkedFramePage = (
  link: string | null
): FramePageRequest | undefined => {
  if (!link) {
    return undefined
  }

  const offset = Number(new URL(link).searchParams.get('offset') ?? 0)

  return { offset: Number.isInteger(offset) && offset > 0 ? offset : 0 }
}

/** 1-based positions of a page's first and last frames, for "frames i–j of N". */
export const getFrameRange = (frames: OccurrenceFrame[]) =>
  frames.length
    ? {
        start: frames[0].frameIndex + 1,
        end: frames[frames.length - 1].frameIndex + 1,
      }
    : undefined
