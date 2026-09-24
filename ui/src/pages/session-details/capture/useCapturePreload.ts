import { useQueryClient } from '@tanstack/react-query'
import { API_ROUTES } from 'data-services/constants'
import { useFetchCaptureDetails } from 'data-services/hooks/captures/useFetchCaptureDetails'
import {
  CaptureDetails,
  ServerCaptureDetails,
} from 'data-services/models/capture-details'
import { useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { CaptureNeighbourIds, demandBand, planPreload } from './capture-preload'
import { buildTierLadder, pickTier } from './capture-tiers'

/**
 * Warms what the next steps of a review need: the capture detail queries of the
 * neighbouring captures, and their image at the tier this view would render.
 *
 * @param demand Device pixels the view asks of an image, so a warmed image is
 * the one the ladder will pick rather than a size nothing requests. Zooming
 * past a thumbnail size warms the neighbours again at the new tier.
 * @param enabled Pass false until the capture on screen has loaded, so a
 * preload never competes with it for bandwidth.
 */
export const useCapturePreload = ({
  captureId,
  demand,
  enabled,
}: {
  captureId?: string
  demand: number
  enabled: boolean
}) => {
  const { projectId } = useParams()
  const queryClient = useQueryClient()
  const fetchCapture = useFetchCaptureDetails(projectId as string)
  const demandRef = useRef(demand)
  demandRef.current = demand
  const warmedRef = useRef(new Set<string>())

  useEffect(() => {
    if (!enabled || !captureId || !projectId) {
      return
    }

    let cancelled = false
    const attempted = new Set<string>()

    const warm = (capture: CaptureDetails) => {
      const tier = pickTier(
        buildTierLadder(
          { ...capture.thumbnailSizes, original: capture.src },
          capture.width
        ),
        demandRef.current
      )

      if (!tier || warmedRef.current.has(tier.src)) {
        return
      }

      warmedRef.current.add(tier.src)
      new Image().src = tier.src
    }

    const walk = async () => {
      const read = new Map<string, CaptureDetails | undefined>()
      const detail = (id: string) => {
        if (!read.has(id)) {
          const record = queryClient.getQueryData<ServerCaptureDetails>([
            API_ROUTES.CAPTURES,
            id,
            projectId,
          ])
          read.set(id, record ? new CaptureDetails(record) : undefined)
        }

        return read.get(id)
      }

      const pending: string[] = []

      planPreload({
        startId: captureId,
        lookup: (id): CaptureNeighbourIds | undefined => detail(id),
      }).forEach((id) => {
        const capture = detail(id)

        if (capture) {
          warm(capture)
        } else if (!attempted.has(id)) {
          attempted.add(id)
          pending.push(id)
        }
      })

      if (!pending.length) {
        return
      }

      const fetched = await Promise.all(
        pending.map((id) => fetchCapture(id).catch(() => undefined))
      )

      if (cancelled) {
        return
      }

      fetched.forEach((capture) => {
        if (capture) {
          warm(capture)
        }
      })

      // The captures just read name the step after them, so walk again.
      walk()
    }

    walk()

    return () => {
      cancelled = true
    }
  }, [
    captureId,
    demandBand(demand),
    enabled,
    fetchCapture,
    projectId,
    queryClient,
  ])
}
