from rest_framework import serializers

from .models import Call, CaseType, Playbook, PlaybookQuestion, Transcript


class CaseTypeSerializer(serializers.ModelSerializer):
    call_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CaseType
        fields = ["id", "name", "description", "call_count"]


class PlaybookQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookQuestion
        fields = ["id", "text", "is_required", "order"]


class PlaybookSerializer(serializers.ModelSerializer):
    questions = PlaybookQuestionSerializer(many=True, read_only=True)
    case_type_name = serializers.CharField(source="case_type.name", read_only=True)

    class Meta:
        model = Playbook
        fields = [
            "id", "name", "description", "case_type", "case_type_name",
            "questions", "created_at", "updated_at",
        ]


class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ["id", "text", "whisper_model", "processing_time_seconds"]


class CallListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view — no transcript, no reasoning."""
    case_type_name = serializers.CharField(
        source="case_type.name", read_only=True, default="Unknown"
    )

    class Meta:
        model = Call
        fields = [
            "id", "call_id", "caller_first_name", "caller_last_name",
            "caller_email", "caller_phone", "case_type", "case_type_name",
            "urgency", "resolution_status", "lead_score",
            "playbook_completeness", "needs_human_review", "summary",
            "created_at",
        ]


class CallDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail view — includes everything."""
    case_type_name = serializers.CharField(
        source="case_type.name", read_only=True, default="Unknown"
    )
    transcript = TranscriptSerializer(read_only=True)

    class Meta:
        model = Call
        fields = [
            "id", "call_id", "audio_file", "duration_seconds", "language",
            "caller_first_name", "caller_last_name", "caller_email",
            "caller_phone", "case_type", "case_type_name", "urgency",
            "key_facts", "summary", "resolution_status",
            "lead_score", "lead_score_reasoning", "resolution_gaps",
            "playbook_completeness", "confidence_scores",
            "needs_human_review", "extraction_accuracy",
            "transcript", "created_at",
        ]
