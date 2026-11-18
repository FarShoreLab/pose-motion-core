// The caller owns the frame returned by takeDue. The queue closes discarded frames.
export class LatestFrameQueue {
  constructor({maxPending = 1} = {}) {
    if (![1, 2].includes(maxPending)) throw Error('maxPending must be 1 or 2');
    this.maxPending = maxPending;
    this.frames = [];
  }

  get frame() { return this.frames[0] ?? null; }
  get size() { return this.frames.length; }

  close(frame, reason) {
    frame.row.action = 'skip';
    frame.row.skip_reason = reason;
    frame.bitmap.close();
  }

  offer(frame, now = Infinity) {
    if (this.maxPending === 1) {
      if (this.frame && frame.row.scheduled_release_ms > now) {
        this.close(frame, 'pending_nearest_release_protected');
        return false;
      }
      if (this.frame) this.discard('superseded_pending_latest');
      this.frames = [frame];
      frame.row.action = 'queued';
      return true;
    }
    const candidates = [...this.frames, frame].sort((a, b) => a.row.scheduled_release_ms - b.row.scheduled_release_ms);
    let keep = candidates;
    if (candidates.length > this.maxPending) {
      const due = candidates.filter(item => item.row.scheduled_release_ms <= now);
      const future = candidates.filter(item => item.row.scheduled_release_ms > now);
      // Preserve the latest eligible frame and nearest future frame.
      if (due.length && future.length) keep = [due.at(-1), future[0]];
      else if (due.length) keep = due.slice(-2);
      else keep = future.slice(0, 2);
      for (const item of candidates) {
        if (!keep.includes(item)) {
          this.close(item, item.row.scheduled_release_ms > now ? 'pending_future_capacity' : 'superseded_pending_latest');
        }
      }
    }
    this.frames = keep;
    if (!keep.includes(frame)) return false;
    frame.row.action = 'queued';
    return true;
  }

  discard(reason) {
    for (const frame of this.frames) this.close(frame, reason);
    this.frames = [];
  }

  takeDue(now) {
    const due = this.frames.filter(frame => frame.row.scheduled_release_ms <= now);
    if (!due.length) return null;
    this.frames = this.frames.filter(frame => frame.row.scheduled_release_ms > now);
    for (const frame of due.slice(0, -1)) this.close(frame, 'superseded_due_at_dispatch');
    return due.at(-1);
  }
}
