from django.db import models


class CaseType(models.Model):
    """Legal case categories (e.g., Divorce, Traffic, Employment)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Playbook(models.Model):
    """Configurable intake requirements per case type.

    Lawyers define what information Marie should collect for each
    type of legal case. This is the "Procedures" concept from Intercom Fin
    applied to legal phone intake.
    """
    case_type = models.OneToOneField(
        CaseType, on_delete=models.CASCADE, related_name='playbook'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.case_type})"


class PlaybookQuestion(models.Model):
    """A required or optional intake question within a playbook."""
    playbook = models.ForeignKey(
        Playbook, on_delete=models.CASCADE, related_name='questions'
    )
    text = models.CharField(max_length=500)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class Call(models.Model):
    """Central model: a phone call processed through the agentic pipeline.

    Fields are denormalized (agent outputs stored directly) because:
    - Only 30 records in POC — no join overhead concern
    - Single query gets everything the dashboard needs
    """

    class ResolutionStatus(models.TextChoices):
        RESOLVED = 'resolved', 'Resolved'
        NEEDS_FOLLOWUP = 'needs_followup', 'Needs Follow-up'
        APPOINTMENT_BOOKED = 'appointment_booked', 'Appointment Booked'
        DROPPED = 'dropped', 'Dropped / Abandoned'
        UNKNOWN = 'unknown', 'Unknown'

    # Audio metadata
    call_id = models.CharField(max_length=50, unique=True)
    audio_file = models.CharField(max_length=255)
    duration_seconds = models.FloatField(null=True, blank=True)
    language = models.CharField(max_length=10, default='de')
    created_at = models.DateTimeField(auto_now_add=True)

    # Agent 2: Call Analyzer output
    caller_first_name = models.CharField(max_length=100, blank=True)
    caller_last_name = models.CharField(max_length=100, blank=True)
    caller_email = models.EmailField(blank=True)
    caller_phone = models.CharField(max_length=50, blank=True)
    case_type = models.ForeignKey(
        CaseType, null=True, blank=True, on_delete=models.SET_NULL
    )
    urgency = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1 (low) to 5 (critical)"
    )
    key_facts = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    resolution_status = models.CharField(
        max_length=30,
        choices=ResolutionStatus.choices,
        default=ResolutionStatus.UNKNOWN,
    )

    # Agent 3: Lead Intelligence output
    lead_score = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="0-100"
    )
    lead_score_reasoning = models.TextField(blank=True)
    resolution_gaps = models.JSONField(default=list, blank=True)
    playbook_completeness = models.FloatField(
        null=True, blank=True, help_text="0.0 to 1.0"
    )

    # Quality & review
    confidence_scores = models.JSONField(
        default=dict, blank=True,
        help_text='Per-field confidence, e.g. {"first_name": 0.9, "email": 0.6}'
    )
    needs_human_review = models.BooleanField(default=False)

    # Ground truth evaluation
    extraction_accuracy = models.JSONField(
        default=dict, blank=True,
        help_text='Per-field match vs ground_truth, e.g. {"first_name": true}'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        name = f"{self.caller_first_name} {self.caller_last_name}".strip()
        return f"{self.call_id}: {name or 'Unknown'}"


class Transcript(models.Model):
    """Agent 1 output: speech-to-text transcript of a call."""
    call = models.OneToOneField(
        Call, on_delete=models.CASCADE, related_name='transcript'
    )
    text = models.TextField()
    whisper_model = models.CharField(max_length=50, default='base')
    processing_time_seconds = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcript for {self.call.call_id}"
