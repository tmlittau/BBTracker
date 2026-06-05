"""Diary query helpers (comparison / ghost-overlay support)."""
from __future__ import annotations


def latest_photo_for_pose(owner, pose_id):
    """Most recent photo of a pose for the owner (drives the capture ghost overlay)."""
    from .models import ProgressPhoto

    return (
        ProgressPhoto.objects.filter(owner=owner, pose_id=pose_id)
        .order_by("-taken_on", "-created_at")
        .first()
    )


def photos_for_pose(owner, pose_id):
    """All of the owner's photos for a pose, oldest→newest (comparison timeline)."""
    from .models import ProgressPhoto

    return ProgressPhoto.objects.filter(owner=owner, pose_id=pose_id).order_by(
        "taken_on", "created_at"
    )
