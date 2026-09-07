from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from households.models import Household



class Chore(models.Model):
    """
    Core Chore definition supporting one-off and recurring schedules,
    effort ratings, flexible deadlines, and multi-person assignments.
    """

    EFFORT_SMALL = "small"
    EFFORT_MEDIUM = "medium"
    EFFORT_LARGE = "large"

    EFFORT_CHOICES = [
        (EFFORT_SMALL, "Small (1 pt)"),
        (EFFORT_MEDIUM, "Medium (2 pts)"),
        (EFFORT_LARGE, "Large (3 pts)"),
    ]

    EFFORT_POINTS = {
        EFFORT_SMALL: 1,
        EFFORT_MEDIUM: 2,
        EFFORT_LARGE: 3,
    }

    RECURRENCE_NONE = "none"
    RECURRENCE_CALENDAR = "calendar"
    RECURRENCE_INTERVAL = "interval"

    RECURRENCE_CHOICES = [
        (RECURRENCE_NONE, "One-off (None)"),
        (RECURRENCE_CALENDAR, "Calendar (e.g. Days of week)"),
        (RECURRENCE_INTERVAL, "Interval (e.g. Every N days)"),
    ]

    DEADLINE_NONE = "none"
    DEADLINE_SPECIFIC = "specific"
    DEADLINE_FLEXIBLE_WINDOW = "flexible_window"

    DEADLINE_CHOICES = [
        (DEADLINE_NONE, "No Deadline"),
        (DEADLINE_SPECIFIC, "Specific Point / Duration"),
        (DEADLINE_FLEXIBLE_WINDOW, "Flexible Window"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="chores"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    effort_level = models.CharField(
        max_length=20, choices=EFFORT_CHOICES, default=EFFORT_MEDIUM
    )

    # Recurrence configuration
    recurrence_type = models.CharField(
        max_length=20, choices=RECURRENCE_CHOICES, default=RECURRENCE_NONE
    )
    recurrence_rule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Serialized schedule rules (e.g., {'days': ['mon', 'thu']} or {'interval': 7, 'unit': 'days'}).",
    )

    # Deadline configuration
    deadline_mode = models.CharField(
        max_length=20, choices=DEADLINE_CHOICES, default=DEADLINE_NONE
    )
    deadline_window_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration in hours defining the deadline or flexible action window.",
    )

    # Multi-assignee support
    is_multi_assignee = models.BooleanField(
        default=False,
        help_text="Whether this chore requires multiple roommates to independently complete.",
    )
    required_assignees_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of distinct roommates required if multi-assignee is enabled.",
    )

    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.title} ({self.household.name})"

    @property
    def points(self) -> int:
        """Workload points corresponding to the effort level."""
        return self.EFFORT_POINTS.get(self.effort_level, 2)

    @property
    def is_recurring(self) -> bool:
        return self.recurrence_type != self.RECURRENCE_NONE

    def clean(self):
        super().clean()

        # Multi-assignee constraint
        if self.is_multi_assignee:
            if self.required_assignees_count < 2:
                raise ValidationError(
                    {
                        "required_assignees_count": "Multi-assignee chores must require at least 2 assignees."
                    }
                )
        else:
            if self.required_assignees_count != 1:
                self.required_assignees_count = 1

        # Deadline validation
        if self.deadline_mode in [self.DEADLINE_SPECIFIC, self.DEADLINE_FLEXIBLE_WINDOW]:
            if not self.deadline_window_hours or self.deadline_window_hours <= 0:
                raise ValidationError(
                    {
                        "deadline_window_hours": f"Deadline mode '{self.deadline_mode}' requires a positive deadline_window_hours."
                    }
                )
        elif self.deadline_mode == self.DEADLINE_NONE:
            self.deadline_window_hours = None

        # Recurrence validation
        if self.recurrence_type == self.RECURRENCE_CALENDAR:
            if not isinstance(self.recurrence_rule, dict) or "days" not in self.recurrence_rule:
                raise ValidationError(
                    {
                        "recurrence_rule": "Calendar recurrence requires a 'days' list in recurrence_rule."
                    }
                )
        elif self.recurrence_type == self.RECURRENCE_INTERVAL:
            if (
                not isinstance(self.recurrence_rule, dict)
                or "interval" not in self.recurrence_rule
                or "unit" not in self.recurrence_rule
            ):
                raise ValidationError(
                    {
                        "recurrence_rule": "Interval recurrence requires 'interval' and 'unit' in recurrence_rule."
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def calculate_deadline(self, start_time):
        """
        Calculate the deadline datetime given an occurrence start time.
        Returns None if no deadline mode is set.
        """
        if self.deadline_mode == self.DEADLINE_NONE or not self.deadline_window_hours:
            return None
        return start_time + timedelta(hours=self.deadline_window_hours)


def default_suggestion_expiry():
    return timezone.now() + timedelta(days=7)


class ChoreSuggestion(models.Model):
    """
    Anonymous chore suggestion proposed by an active roommate.
    The creator's identity is strictly anonymous to roommates and API consumers.
    Requires majority approval from active roommates to become an active Chore.
    Expires automatically after a fixed period if not reviewed.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_EXPIRED, "Expired"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="suggestions"
    )
    # Stored for internal tracking, NEVER exposed to users/API
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_suggestions",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    effort_level = models.CharField(
        max_length=20, choices=Chore.EFFORT_CHOICES, default=Chore.EFFORT_MEDIUM
    )
    recurrence_type = models.CharField(
        max_length=20, choices=Chore.RECURRENCE_CHOICES, default=Chore.RECURRENCE_NONE
    )
    recurrence_rule = models.JSONField(default=dict, blank=True)
    deadline_mode = models.CharField(
        max_length=20, choices=Chore.DEADLINE_CHOICES, default=Chore.DEADLINE_NONE
    )
    deadline_window_hours = models.PositiveIntegerField(null=True, blank=True)
    is_multi_assignee = models.BooleanField(default=False)
    required_assignees_count = models.PositiveIntegerField(default=1)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    approved_chore = models.OneToOneField(
        Chore,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_suggestion",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_suggestion_expiry)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Suggestion: {self.title} ({self.household.name}) - {self.status}"

    def check_expiration(self, current_time=None):
        """Transition unreviewed proposal to expired if expiry time has passed."""
        if self.status != self.STATUS_PENDING:
            return self.status

        now = current_time or timezone.now()
        if now >= self.expires_at:
            self.status = self.STATUS_EXPIRED
            self.save(update_fields=["status", "updated_at"])
        return self.status

    def evaluate_votes(self):
        """
        Evaluate majority vote across all active household roommates.
        Threshold: strictly greater than 50% of active members (i.e. (N // 2) + 1).
        If threshold reached, converts suggestion to an active Chore automatically.
        """
        if self.status != self.STATUS_PENDING:
            return self.status

        # Check if already expired
        if self.check_expiration() == self.STATUS_EXPIRED:
            return self.status

        active_members = self.household.get_active_members()
        total_active_count = active_members.count()
        if total_active_count == 0:
            return self.status

        majority_needed = (total_active_count // 2) + 1
        active_user_ids = set(active_members.values_list("user_id", flat=True))

        valid_votes = self.votes.filter(voter_id__in=active_user_ids)
        approve_count = valid_votes.filter(approved=True).count()
        reject_count = valid_votes.filter(approved=False).count()

        if approve_count >= majority_needed:
            # Majority approval reached! Automatically convert into active Chore
            self.status = self.STATUS_APPROVED
            chore = Chore.objects.create(
                household=self.household,
                title=self.title,
                description=self.description,
                effort_level=self.effort_level,
                recurrence_type=self.recurrence_type,
                recurrence_rule=self.recurrence_rule,
                deadline_mode=self.deadline_mode,
                deadline_window_hours=self.deadline_window_hours,
                is_multi_assignee=self.is_multi_assignee,
                required_assignees_count=self.required_assignees_count,
            )
            self.approved_chore = chore
            self.save(update_fields=["status", "approved_chore", "updated_at"])
            return self.status

        # If reject votes make majority mathematically impossible
        max_possible_approvals = total_active_count - reject_count
        if max_possible_approvals < majority_needed:
            self.status = self.STATUS_REJECTED
            self.save(update_fields=["status", "updated_at"])

        return self.status


class ChoreSuggestionVote(models.Model):
    """Vote on an anonymous chore suggestion."""

    suggestion = models.ForeignKey(
        ChoreSuggestion, on_delete=models.CASCADE, related_name="votes"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="suggestion_votes",
    )
    approved = models.BooleanField()
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("suggestion", "voter")

    def __str__(self):
        vote_str = "Approve" if self.approved else "Reject"
        return f"{self.voter}: {vote_str} for {self.suggestion.title}"


class ChoreOccurrence(models.Model):
    """
    Occurrence lifecycle model representing a concrete instance of a chore.
    Tracks states: Upcoming, Active, Completed, Missed, Completed Late, Disputed.
    """

    STATUS_UPCOMING = "upcoming"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_MISSED = "missed"
    STATUS_COMPLETED_LATE = "completed_late"
    STATUS_DISPUTED = "disputed"

    STATUS_CHOICES = [
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_MISSED, "Missed"),
        (STATUS_COMPLETED_LATE, "Completed Late"),
        (STATUS_DISPUTED, "Disputed"),
    ]

    chore = models.ForeignKey(
        Chore, on_delete=models.CASCADE, related_name="occurrences"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_UPCOMING
    )
    scheduled_start = models.DateTimeField(
        help_text="Point in time when the action window opens for this occurrence."
    )
    due_date = models.DateTimeField(
        null=True, blank=True, help_text="Deadline timestamp for this occurrence."
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    missed_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when occurrence became past-due and missed."
    )
    was_missed = models.BooleanField(
        default=False,
        help_text="Audit flag permanently preserving that this chore was missed past its deadline.",
    )
    # Verification tracking fields
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this chore completion was formally verified by a roommate.",
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_occurrences",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True, default="")

    # Audit-preserving dispute tracking fields
    is_disputed = models.BooleanField(
        default=False,
        help_text="Whether this completion is flagged as disputed.",
    )
    disputed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputed_occurrences",
    )
    disputed_at = models.DateTimeField(null=True, blank=True)
    dispute_reason = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_start", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["chore"],
                condition=models.Q(status="upcoming"),
                name="unique_upcoming_occurrence_per_chore",
            )
        ]

    def __str__(self):
        return f"{self.chore.title} ({self.status}) @ {self.scheduled_start.strftime('%Y-%m-%d %H:%M')}"

    @property
    def is_actionable(self):
        return self.status in [self.STATUS_ACTIVE, self.STATUS_MISSED]

    def activate(self):
        """Transition from UPCOMING to ACTIVE when window opens."""
        if self.status == self.STATUS_UPCOMING:
            self.status = self.STATUS_ACTIVE
            self.save(update_fields=["status", "updated_at"])

    def mark_missed(self, missed_time=None):
        """Transition from ACTIVE to MISSED when deadline expires."""
        if self.status == self.STATUS_ACTIVE:
            now = missed_time or timezone.now()
            self.status = self.STATUS_MISSED
            self.was_missed = True
            self.missed_at = now
            self.save(update_fields=["status", "was_missed", "missed_at", "updated_at"])
            # Record missed state on assignments to preserve responsible roommate statistics
            for assignment in self.assignments.all():
                assignment.was_missed = True
                assignment.missed_at = now
                assignment.save(update_fields=["was_missed", "missed_at", "updated_at"])

    def complete(self, completed_time=None):
        """Transition to COMPLETED or COMPLETED_LATE."""
        now = completed_time or timezone.now()
        if self.status == self.STATUS_MISSED or self.was_missed:
            self.status = self.STATUS_COMPLETED_LATE
        else:
            self.status = self.STATUS_COMPLETED
        self.completed_at = now
        self.save(update_fields=["status", "completed_at", "updated_at"])

    def verify(self, verified_by, notes="", verified_time=None):
        """Formally record roommate completion verification."""
        if self.status not in [self.STATUS_COMPLETED, self.STATUS_COMPLETED_LATE]:
            raise ValueError(f"Cannot verify an occurrence with status '{self.status}'.")
        now = verified_time or timezone.now()
        self.is_verified = True
        self.verified_by = verified_by
        self.verified_at = now
        self.verification_notes = notes
        self.save(
            update_fields=[
                "is_verified",
                "verified_by",
                "verified_at",
                "verification_notes",
                "updated_at",
            ]
        )

    def dispute(self, disputed_by=None, reason="", disputed_time=None):
        """
        Transition to DISPUTED while strictly preserving completion timestamps, notes, and proof.
        Audit-preserving dispute mechanism.
        """
        if self.status not in [
            self.STATUS_COMPLETED,
            self.STATUS_COMPLETED_LATE,
            self.STATUS_DISPUTED,
        ]:
            raise ValueError(f"Cannot dispute an occurrence with status '{self.status}'.")
        now = disputed_time or timezone.now()
        self.status = self.STATUS_DISPUTED
        self.is_disputed = True
        if disputed_by:
            self.disputed_by = disputed_by
        if disputed_time or not self.disputed_at:
            self.disputed_at = now
        if reason:
            self.dispute_reason = reason
        self.save(
            update_fields=[
                "status",
                "is_disputed",
                "disputed_by",
                "disputed_at",
                "dispute_reason",
                "updated_at",
            ]
        )

    def resolve_dispute(self, resolved_by=None, resolution_notes=""):
        """Resolve dispute, transitioning back to completed while preserving dispute audit trail."""
        if self.status != self.STATUS_DISPUTED:
            raise ValueError("Only disputed occurrences can have their dispute resolved.")
        self.status = self.STATUS_COMPLETED_LATE if self.was_missed else self.STATUS_COMPLETED
        self.is_disputed = False
        if resolution_notes:
            self.verification_notes = f"Dispute resolved: {resolution_notes}"
        self.save(
            update_fields=[
                "status",
                "is_disputed",
                "verification_notes",
                "updated_at",
            ]
        )


class ChoreAssignment(models.Model):
    """
    Assignment linking a roommate to a chore occurrence.
    For multi-person chores, multiple assignments exist for one occurrence.
    """

    occurrence = models.ForeignKey(
        ChoreOccurrence, on_delete=models.CASCADE, related_name="assignments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chore_assignments",
    )
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    was_missed = models.BooleanField(
        default=False,
        help_text="Audit flag permanently preserving that this assignment was missed past its deadline.",
    )
    missed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    proof_image = models.FileField(
        upload_to="chore_proofs/%Y/%m/",
        null=True,
        blank=True,
        help_text="Uploaded photo evidence of chore completion.",
    )
    original_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="original_chore_assignments",
        help_text="Original assignee before any personal favor chore swap.",
    )
    is_swapped = models.BooleanField(
        default=False,
        help_text="Flag indicating this assignment was swapped as a personal favor.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("occurrence", "user")
        ordering = ["created_at"]

    def __str__(self):
        comp_str = "Done" if self.completed else "Pending"
        return f"{self.user} -> {self.occurrence.chore.title} ({comp_str})"


class ChoreSwapRequest(models.Model):
    """
    Mutual chore swap request model allowing roommates to propose and accept/decline
    occurrence swaps as personal favors, leaving 8-week fairness calculations unaffected.
    """

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="swap_requests"
    )
    proposer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposed_swaps",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_swaps",
    )
    proposer_occurrence = models.ForeignKey(
        ChoreOccurrence,
        on_delete=models.CASCADE,
        related_name="proposer_swaps",
        help_text="Chore occurrence offered by the proposer.",
    )
    recipient_occurrence = models.ForeignKey(
        ChoreOccurrence,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recipient_swaps",
        help_text="Chore occurrence requested from recipient in exchange (optional).",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Swap: {self.proposer} <-> {self.recipient} ({self.status})"

    def accept(self, user=None):
        """
        Accept the swap request with mutual agreement.
        Swaps the assigned roommates on the respective occurrences while
        preserving original_user so 8-week fairness calculations remain unaffected.
        """
        if self.status != self.STATUS_PENDING:
            raise ValueError(f"Cannot accept swap request with status '{self.status}'.")
        if user and user != self.recipient:
            raise ValueError("Only the recipient can accept a swap request.")

        now = timezone.now()

        # 1. Update proposer assignment -> reassign to recipient
        proposer_assignment = self.proposer_occurrence.assignments.filter(
            user=self.proposer
        ).first()
        if not proposer_assignment:
            raise ValueError("Proposer is no longer assigned to the offered chore occurrence.")

        # If recipient is already assigned to proposer_occurrence (multi-assignee), remove duplicate
        existing_recip = self.proposer_occurrence.assignments.filter(user=self.recipient).first()
        if existing_recip:
            existing_recip.delete()

        proposer_assignment.original_user = (
            proposer_assignment.original_user or proposer_assignment.user
        )
        proposer_assignment.user = self.recipient
        proposer_assignment.is_swapped = True
        proposer_assignment.save(
            update_fields=["original_user", "user", "is_swapped", "updated_at"]
        )

        # 2. Update recipient assignment if 2-way swap
        if self.recipient_occurrence:
            recipient_assignment = self.recipient_occurrence.assignments.filter(
                user=self.recipient
            ).first()
            if not recipient_assignment:
                raise ValueError(
                    "Recipient is no longer assigned to the requested chore occurrence."
                )

            existing_prop = self.recipient_occurrence.assignments.filter(
                user=self.proposer
            ).first()
            if existing_prop:
                existing_prop.delete()

            recipient_assignment.original_user = (
                recipient_assignment.original_user or recipient_assignment.user
            )
            recipient_assignment.user = self.proposer
            recipient_assignment.is_swapped = True
            recipient_assignment.save(
                update_fields=["original_user", "user", "is_swapped", "updated_at"]
            )

        self.status = self.STATUS_ACCEPTED
        self.responded_at = now
        self.save(update_fields=["status", "responded_at", "updated_at"])
        return self

    def decline(self, user=None):
        """Explicitly decline the swap request."""
        if self.status != self.STATUS_PENDING:
            raise ValueError(f"Cannot decline swap request with status '{self.status}'.")
        if user and user != self.recipient:
            raise ValueError("Only the recipient can decline a swap request.")

        self.status = self.STATUS_DECLINED
        self.responded_at = timezone.now()
        self.save(update_fields=["status", "responded_at", "updated_at"])
        return self

    def cancel(self, user=None):
        """Proposer cancels the pending swap request."""
        if self.status != self.STATUS_PENDING:
            raise ValueError(f"Cannot cancel swap request with status '{self.status}'.")
        if user and user != self.proposer:
            raise ValueError("Only the proposer can cancel a swap request.")

        self.status = self.STATUS_CANCELLED
        self.save(update_fields=["status", "updated_at"])
        return self


