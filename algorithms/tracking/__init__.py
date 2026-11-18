"""Target association over caller-provided detections and embeddings."""
from .conflict import ConflictTracker, offline_link
from .identity import TargetPolicy, GalleryTargetPolicy
from .policies import conflict_config, identity_config

__all__ = ['ConflictTracker', 'offline_link', 'TargetPolicy',
           'GalleryTargetPolicy', 'conflict_config', 'identity_config']
