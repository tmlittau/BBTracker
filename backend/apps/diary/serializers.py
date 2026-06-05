from rest_framework import serializers

from .models import CheckIn, Pose, ProgressPhoto


class PoseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pose
        fields = ["id", "name", "slug", "view", "order"]


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = [
            "id", "date", "bodyweight",
            "energy", "sleep", "mood", "motivation", "soreness",
            "notes", "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        # Bodyweight is mandatory on create; an empty value defaults to 0. The
        # model stays nullable so historical rows are untouched, and PATCH leaves
        # unspecified fields alone.
        if not self.partial and attrs.get("bodyweight") in (None, ""):
            attrs["bodyweight"] = 0
        return attrs


class ProgressPhotoSerializer(serializers.ModelSerializer):
    pose_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()

    class Meta:
        model = ProgressPhoto
        fields = [
            "id", "pose", "pose_name", "taken_on", "notes",
            "width", "height", "bytes", "content_type",
            "image_url", "thumb_url", "created_at",
        ]
        read_only_fields = fields

    def get_pose_name(self, obj) -> str:
        return obj.pose.name if obj.pose else ""

    def get_image_url(self, obj) -> str:
        return f"/api/v1/diary/photos/{obj.id}/image/"

    def get_thumb_url(self, obj) -> str:
        return f"/api/v1/diary/photos/{obj.id}/image/?variant=thumb"


class ProgressPhotoUploadSerializer(serializers.Serializer):
    """Validates multipart upload input; the view does storage + processing."""

    image = serializers.ImageField(write_only=True)
    pose = serializers.PrimaryKeyRelatedField(
        queryset=Pose.objects.all(), required=False, allow_null=True
    )
    taken_on = serializers.DateField()
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)
