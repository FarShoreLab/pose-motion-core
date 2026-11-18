"""Pure timestamp bookkeeping; never reads images or stores pose output."""
import math

class EpochClock:
    def __init__(self, policy='cold'):
        if policy not in ('cold', 'warm'):
            raise ValueError('Unknown epoch policy')
        self.policy = policy
        self.epoch = None
        self.last_model_ms = -1
        self.last_source_ms = None
        self.source_start_ms = None
        self.offset_ms = 0

    def prepare(self, epoch):
        if self.epoch == epoch:
            return False
        self.epoch = epoch
        self.last_source_ms = None
        self.source_start_ms = None
        if self.policy == 'cold':
            self.last_model_ms = -1
            self.offset_ms = 0
        return True

    def map(self, source_ms, source_fps):
        if not math.isfinite(source_ms) or source_ms < 0 or not math.isfinite(source_fps) or source_fps <= 0:
            raise ValueError('Invalid source clock')
        if self.last_source_ms is not None and source_ms <= self.last_source_ms:
            raise ValueError('source_pts_ms must increase within an epoch')
        source_rounded = round(source_ms)
        if self.last_source_ms is None:
            step = max(1, round(1000 / source_fps))
            self.offset_ms = max(0, self.last_model_ms + step - source_rounded) if self.policy == 'warm' and self.last_model_ms >= 0 else 0
        timestamp = source_rounded + self.offset_ms
        if timestamp <= self.last_model_ms:
            raise ValueError('Rounded model timestamp must increase; source samples are too close')
        return {'model_timestamp_ms': timestamp, 'source_pts_rounded_ms': source_rounded,
                'model_epoch_offset_ms': self.offset_ms,
                'previous_model_timestamp_ms': self.last_model_ms,
                'epoch_source_pts_start_ms': source_ms if self.source_start_ms is None else self.source_start_ms}

    def commit(self, source_ms, model_ms):
        if self.last_source_ms is None:
            self.source_start_ms = source_ms
        self.last_source_ms = source_ms
        self.last_model_ms = model_ms
