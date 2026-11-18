"""Policy constants from the archived experiments; no clip or initialization data."""
from copy import deepcopy

CONFLICT = {
    "detector_confidence_min": 0.25,
    "clear_anchor_frames": 3,
    "duplicate_iou": 0.85,
    "duplicate_cosine": 0.8,
    "overlap_clue_min_fraction": 0.25,
    "center_clue_width_fraction": 0.75,
    "local_assignment_margin": 0.05,
    "microtrack_max_gap": 3,
    "association_appearance_weight": 0.65,
    "association_motion_weight": 0.2,
    "association_scale_weight": 0.1,
    "association_direction_weight": 0.05,
    "unmatched_cost_per_endpoint": 0.35,
    "joint_assignment_min_gap": 0.1,
    "joint_assignment_similarity_floor": 0.35,
    "max_reconnect_gap_frames": 90,
    "gallery_max": 32
}

IDENTITY = {
    "v1": {
        "anchor_similarity_min": 0.7,
        "negative_margin_min": 0.05,
        "candidate_margin_min": 0.06,
        "reacquire_similarity_min": 0.78,
        "reacquire_confirmation_frames": 2,
        "minimum_detection_confidence": 0.2,
        "max_center_motion_diagonals": 1.25,
        "max_size_ratio": 2.5,
        "motion_grace_frames": 15,
        "max_prediction_frames": 5,
        "template_anchor_similarity_min": 0.85,
        "template_detection_confidence_min": 0.65,
        "template_negative_margin_min": 0.15,
        "template_max_other_overlap": 0.15,
        "template_update_interval_frames": 10,
        "template_gallery_max": 8,
        "seed_bbox_iou_min": 0.5
    },
    "v2": {
        "anchor_similarity_min": 0.7,
        "negative_margin_min": 0.08,
        "candidate_margin_min": 0.06,
        "reacquire_similarity_min": 0.78,
        "reacquire_confirmation_frames": 2,
        "minimum_detection_confidence": 0.2,
        "max_center_motion_diagonals": 1.25,
        "max_size_ratio": 2.0,
        "motion_grace_frames": 15,
        "max_prediction_frames": 5,
        "template_anchor_similarity_min": 0.4,
        "template_detection_confidence_min": 0.65,
        "template_negative_margin_min": 0.2,
        "template_max_other_overlap": 0.15,
        "template_update_interval_frames": 10,
        "template_gallery_max": 32,
        "anchor_similarity_floor": 0.25,
        "gallery_similarity_min": 0.65,
        "long_gap_similarity_min": 0.75,
        "long_gap_frames": 30,
        "maximum_observation_overlap": 0.5,
        "overlap_detection_confidence": 0.25,
        "template_gallery_similarity_min": 0.8,
        "template_candidate_margin_min": 0.15,
        "seed_bbox_iou_min": 0.5
    },
    "v3": {
        "anchor_similarity_min": 0.7,
        "negative_margin_min": 0.08,
        "candidate_margin_min": 0.06,
        "reacquire_similarity_min": 0.78,
        "reacquire_confirmation_frames": 2,
        "minimum_detection_confidence": 0.2,
        "max_center_motion_diagonals": 1.25,
        "max_size_ratio": 2.0,
        "motion_grace_frames": 15,
        "max_prediction_frames": 5,
        "template_anchor_similarity_min": 0.3,
        "template_detection_confidence_min": 0.65,
        "template_negative_margin_min": 0.2,
        "template_max_other_overlap": 0.15,
        "template_update_interval_frames": 10,
        "template_gallery_max": 32,
        "anchor_similarity_floor": 0.25,
        "gallery_similarity_min": 0.65,
        "long_gap_similarity_min": 0.65,
        "long_gap_frames": 30,
        "maximum_observation_overlap": 0.5,
        "overlap_detection_confidence": 0.25,
        "template_gallery_similarity_min": 0.65,
        "template_candidate_margin_min": 0.15,
        "seed_bbox_iou_min": 0.5
    }
}

def conflict_config():
    """Return independent conflict-tracklet v1 parameters."""
    return deepcopy(CONFLICT)


def identity_config(version='v3'):
    """Return identity parameters for TargetPolicy v1 or GalleryTargetPolicy v2/v3."""
    return deepcopy(IDENTITY[version])
