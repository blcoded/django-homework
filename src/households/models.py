import secrets
from django.conf import settings
from django.db import models


def generate_invite_code():
    return secrets.token_urlsafe(16)


class Household(models.Model):
    """
    Shared household model storing configuration flags, timezone,
    and unique invite code for prospective roommates.
    """

    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=50, default="UTC")
    require_join_approval = models.BooleanField(
        default=False,
        help_text="Whether prospective members require household approval before joining.",
    )
    require_completion_verification = models.BooleanField(
        default=False,
        help_text="Whether chore completions require roommate verification.",
    )
    invite_code = models.CharField(
        max_length=64, unique=True, default=generate_invite_code
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def regenerate_invite_code(self):
        self.invite_code = generate_invite_code()
        self.save(update_fields=["invite_code", "updated_at"])
        return self.invite_code

    def get_active_members(self):
        return self.members.filter(status=HouseholdMember.STATUS_ACTIVE)


class HouseholdMember(models.Model):
    """
    Household membership model with equal permissions for all active members.
    There are no admin or boss roles.
    """

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_DEPARTED = "departed"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_DEPARTED, "Departed"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="household_memberships",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("household", "user")
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} in {self.household.name} ({self.status})"


class JoinRequest(models.Model):
    """Request by a prospective roommate to join a household."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="join_requests"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"JoinRequest: {self.user} -> {self.household.name} ({self.status})"

    def evaluate_votes(self):
        """
        Enforce unanimous consent: All current active members must approve.
        If any active member rejects, request is rejected.
        """
        if self.status != self.STATUS_PENDING:
            return self.status

        active_members = self.household.get_active_members()
        active_user_ids = set(active_members.values_list("user_id", flat=True))

        votes = self.votes.filter(voter_id__in=active_user_ids)
        if votes.filter(approved=False).exists():
            self.status = self.STATUS_REJECTED
            self.save(update_fields=["status", "updated_at"])
            return self.status

        approved_voter_ids = set(
            votes.filter(approved=True).values_list("voter_id", flat=True)
        )
        if active_user_ids.issubset(approved_voter_ids) and len(active_user_ids) > 0:
            self.status = self.STATUS_APPROVED
            self.save(update_fields=["status", "updated_at"])
            # Enroll user into household as active member
            HouseholdMember.objects.update_or_create(
                household=self.household,
                user=self.user,
                defaults={"status": HouseholdMember.STATUS_ACTIVE},
            )
        return self.status


class JoinRequestVote(models.Model):
    """Vote cast by an active household member on a join request."""

    join_request = models.ForeignKey(
        JoinRequest, on_delete=models.CASCADE, related_name="votes"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="join_votes"
    )
    approved = models.BooleanField()
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("join_request", "voter")

    def __str__(self):
        decision = "Approve" if self.approved else "Reject"
        return f"{self.voter}: {decision} for {self.join_request}"


class LeaveRequest(models.Model):
    """Request by an existing active roommate to leave the household."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    household = models.ForeignKey(
        Household, on_delete=models.CASCADE, related_name="leave_requests"
    )
    member = models.ForeignKey(
        HouseholdMember, on_delete=models.CASCADE, related_name="leave_requests"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"LeaveRequest: {self.member.user} from {self.household.name} ({self.status})"

    def evaluate_votes(self):
        """
        Enforce unanimous consent from all other active members in the household.
        If no other active members exist, request auto-approves.
        """
        if self.status != self.STATUS_PENDING:
            return self.status

        other_active_members = self.household.get_active_members().exclude(
            id=self.member_id
        )
        other_active_user_ids = set(
            other_active_members.values_list("user_id", flat=True)
        )

        if len(other_active_user_ids) == 0:
            # Solo member leaving
            self.status = self.STATUS_APPROVED
            self.save(update_fields=["status", "updated_at"])
            self.member.status = HouseholdMember.STATUS_DEPARTED
            self.member.save(update_fields=["status", "updated_at"])
            return self.status

        votes = self.votes.filter(voter_id__in=other_active_user_ids)
        if votes.filter(approved=False).exists():
            self.status = self.STATUS_REJECTED
            self.save(update_fields=["status", "updated_at"])
            return self.status

        approved_voter_ids = set(
            votes.filter(approved=True).values_list("voter_id", flat=True)
        )
        if other_active_user_ids.issubset(approved_voter_ids):
            self.status = self.STATUS_APPROVED
            self.save(update_fields=["status", "updated_at"])
            self.member.status = HouseholdMember.STATUS_DEPARTED
            self.member.save(update_fields=["status", "updated_at"])

        return self.status


class LeaveRequestVote(models.Model):
    """Vote cast by another active roommate on a leave request."""

    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="votes"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_votes"
    )
    approved = models.BooleanField()
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("leave_request", "voter")

    def __str__(self):
        decision = "Approve" if self.approved else "Reject"
        return f"{self.voter}: {decision} for {self.leave_request}"
