export type ServerTimelineTick = {
  start: string
  end: string
  first_capture: {
    id: number
  } | null
  top_capture: {
    id: number
  } | null
  captures_count: number
  detections_count: number
  detections_avg: number
  was_processed: boolean
}

export class TimelineTick {
  private readonly _timelineTick: ServerTimelineTick

  public constructor(timelineTick: ServerTimelineTick) {
    this._timelineTick = timelineTick
  }

  get endDate(): Date {
    return new Date(this._timelineTick.end)
  }

  get numDetections(): number {
    return this._timelineTick.detections_count ?? 0
  }

  get avgDetections(): number {
    return this._timelineTick.detections_avg ?? 0
  }

  get wasProcessed(): boolean {
    return this._timelineTick.was_processed
  }

  get numCaptures(): number {
    return this._timelineTick.captures_count ?? 0
  }

  get startDate(): Date {
    return new Date(this._timelineTick.start)
  }

  get firstCaptureId(): string | undefined {
    if (!this._timelineTick.first_capture) {
      return undefined
    }

    return `${this._timelineTick.first_capture.id}`
  }

  get topCaptureId(): string | undefined {
    if (!this._timelineTick.top_capture) {
      return undefined
    }

    return `${this._timelineTick.top_capture.id}`
  }

  get representativeCaptureId(): string | undefined {
    return this.topCaptureId ?? this.firstCaptureId
  }
}
