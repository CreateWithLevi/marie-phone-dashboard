from django.db.models import Avg, Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from .models import Call, CaseType, Playbook, PlaybookQuestion
from .serializers import (
    CallDetailSerializer,
    CallListSerializer,
    CaseTypeSerializer,
    PlaybookQuestionSerializer,
    PlaybookSerializer,
)


class CallViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve calls with filtering and sorting.

    Query params:
        case_type: filter by case type ID
        resolution_status: filter by status
        needs_review: filter by human review flag (true/false)
        urgency_min: minimum urgency
        search: search in caller name, email, summary
        ordering: sort field (prepend - for desc)
    """
    queryset = Call.objects.select_related("case_type", "transcript").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CallDetailSerializer
        return CallListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        # Filters
        if case_type := params.get("case_type"):
            qs = qs.filter(case_type_id=case_type)

        if status := params.get("resolution_status"):
            qs = qs.filter(resolution_status=status)

        if params.get("needs_review") == "true":
            qs = qs.filter(needs_human_review=True)

        if urgency_min := params.get("urgency_min"):
            qs = qs.filter(urgency__gte=int(urgency_min))

        if search := params.get("search"):
            qs = qs.filter(
                Q(caller_first_name__icontains=search)
                | Q(caller_last_name__icontains=search)
                | Q(caller_email__icontains=search)
                | Q(summary__icontains=search)
            )

        # Sorting
        ordering = params.get("ordering", "-lead_score")
        allowed = {
            "lead_score", "-lead_score",
            "urgency", "-urgency",
            "call_id", "-call_id",
            "playbook_completeness", "-playbook_completeness",
            "created_at", "-created_at",
        }
        if ordering in allowed:
            qs = qs.order_by(ordering)

        return qs


class PlaybookViewSet(viewsets.ModelViewSet):
    """CRUD for playbooks with nested questions."""
    queryset = Playbook.objects.select_related("case_type").prefetch_related("questions").all()
    serializer_class = PlaybookSerializer

    @action(detail=True, methods=["post"])
    def add_question(self, request, pk=None):
        """Add a question to a playbook."""
        playbook = self.get_object()
        text = request.data.get("text", "").strip()
        if not text:
            return Response({"error": "text is required"}, status=status.HTTP_400_BAD_REQUEST)

        max_order = playbook.questions.count()
        question = PlaybookQuestion.objects.create(
            playbook=playbook,
            text=text,
            is_required=request.data.get("is_required", True),
            order=max_order,
        )
        return Response(PlaybookQuestionSerializer(question).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="remove_question/(?P<question_id>[0-9]+)")
    def remove_question(self, request, pk=None, question_id=None):
        """Remove a question from a playbook."""
        playbook = self.get_object()
        try:
            question = playbook.questions.get(id=question_id)
            question.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PlaybookQuestion.DoesNotExist:
            return Response({"error": "Question not found"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def dashboard_stats(request):
    """Aggregated KPIs for the dashboard."""
    calls = Call.objects.all()
    total = calls.count()

    if total == 0:
        return Response({"total_calls": 0})

    # Resolution funnel
    resolution_counts = dict(
        calls.values_list("resolution_status")
        .annotate(count=Count("id"))
        .values_list("resolution_status", "count")
    )

    # Case type breakdown
    case_type_counts = list(
        calls.filter(case_type__isnull=False)
        .values("case_type__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Lead score distribution
    score_ranges = {
        "high": calls.filter(lead_score__gte=80).count(),
        "good": calls.filter(lead_score__gte=60, lead_score__lt=80).count(),
        "moderate": calls.filter(lead_score__gte=40, lead_score__lt=60).count(),
        "low": calls.filter(lead_score__lt=40).count(),
    }

    # Averages
    avgs = calls.aggregate(
        avg_lead_score=Avg("lead_score"),
        avg_urgency=Avg("urgency"),
        avg_playbook_completeness=Avg("playbook_completeness"),
    )

    return Response({
        "total_calls": total,
        "needs_review": calls.filter(needs_human_review=True).count(),
        "resolution_funnel": resolution_counts,
        "case_type_breakdown": case_type_counts,
        "lead_score_distribution": score_ranges,
        "avg_lead_score": round(avgs["avg_lead_score"] or 0, 1),
        "avg_urgency": round(avgs["avg_urgency"] or 0, 1),
        "avg_playbook_completeness": round(avgs["avg_playbook_completeness"] or 0, 2),
    })


@api_view(["GET"])
def evaluation_report(request):
    """Ground truth comparison report."""
    calls = Call.objects.exclude(extraction_accuracy={}).all()

    if not calls.exists():
        return Response({"message": "No evaluation data available"})

    results = []
    field_accuracy = {"first_name": 0, "last_name": 0, "email": 0, "phone": 0}
    total = 0

    for call in calls:
        acc = call.extraction_accuracy
        if not acc:
            continue
        total += 1
        for field in field_accuracy:
            if acc.get(field):
                field_accuracy[field] += 1

        results.append({
            "call_id": call.call_id,
            "accuracy": acc,
            "confidence_scores": call.confidence_scores,
        })

    # Calculate percentages
    if total > 0:
        field_accuracy_pct = {
            field: round(count / total * 100, 1)
            for field, count in field_accuracy.items()
        }
    else:
        field_accuracy_pct = field_accuracy

    return Response({
        "total_evaluated": total,
        "field_accuracy_percent": field_accuracy_pct,
        "per_call": results,
    })
