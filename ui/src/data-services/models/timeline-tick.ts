import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'

export type ServerTimelineTick = {
  start: string
  end: string
  first_capture: {
    id: number
  } | null
  captures_count: number
  detections_count: number
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

  get numCaptures(): number {
    return this._timelineTick.captures_count ?? 0
  }
  j

  get startDate(): Date {
    return new Date(this._timelineTick.start)
  }

  get firstCaptureId(): string | undefined {
    if (!this._timelineTick.first_capture) {
      return undefined
    }

    return `${this._timelineTick.first_capture.id}`
  }

  get tooltip(): string {
    const timespanString = getCompactTimespanString({
      date1: this.startDate,
      date2: this.endDate,
      options: {
        second: true,
      },
    })

    return `${timespanString}<br>Captures: ${this.numCaptures}<br>Detections: ${this.numDetections}`
  }
}
