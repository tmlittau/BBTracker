from rest_framework import serializers

from .models import Profile, User


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["sex", "date_of_birth", "height_cm", "unit_system", "timezone"]


class UserSerializer(serializers.ModelSerializer):
    # Writable nested profile so PATCH /me/ can update it. All profile fields have
    # model defaults / are nullable, so each is optional → partial updates work.
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "profile"]
        read_only_fields = ["id", "email"]

    def update(self, instance, validated_data):
        """Update the user and, if present, the nested one-to-one Profile.

        Always operates on the serializer's `instance` (the request user in
        MeView), so a user can only ever edit their own profile.
        """
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance
