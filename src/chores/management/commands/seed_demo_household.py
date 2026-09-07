from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from activity.models import ActivityLog
from activity.services import ActivityService
from chores.models import (
    Chore,
    ChoreAssignment,
    ChoreOccurrence,
    ChoreSuggestion,
    ChoreSuggestionVote,
    ChoreSwapRequest,
)
from households.models import (
    AbsenceRequest,
    AbsenceRequestVote,
    Household,
    HouseholdMember,
)
from stats.services import StatsService

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a comprehensive, realistic demo household with 4 roommates, 8 weeks of history, chores, and interactions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing demo household and demo users before seeding.",
        )
        parser.add_argument(
            "--household-name",
            type=str,
            default="Baker Street 221B",
            help="Name of the demo household.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        household_name = options["household_name"]
        clear = options["clear"]

        demo_emails = [
            "alice@example.com",
            "bob@example.com",
            "charlie@example.com",
            "dana@example.com",
        ]

        if clear:
            self.stdout.write("Clearing existing demo data...")
            Household.objects.filter(name=household_name).delete()
            User.objects.filter(email__in=demo_emails).delete()

        self.stdout.write(f"Seeding demo household: '{household_name}'...")

        # 1. Create or get Demo Users
        users = []
        user_specs = [
            ("alice@example.com", "Alice Smith"),
            ("bob@example.com", "Bob Jones"),
            ("charlie@example.com", "Charlie Brown"),
            ("dana@example.com", "Dana Scully"),
        ]

        for email, name in user_specs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"display_name": name},
            )
            user.display_name = name
            user.set_password("Pass1234!")
            user.save()
            users.append(user)

        alice, bob, charlie, dana = users

        # 2. Create Household
        household, _ = Household.objects.get_or_create(
            name=household_name,
            defaults={"timezone": "UTC", "invite_code": "BAKER-221B"},
        )
        household.invite_code = "BAKER-221B"
        household.save()

        # 3. Add Members
        members = []
        for user in users:
            mem, _ = HouseholdMember.objects.get_or_create(
                household=household,
                user=user,
                defaults={"status": HouseholdMember.STATUS_ACTIVE},
            )
            mem.status = HouseholdMember.STATUS_ACTIVE
            mem.save()
            members.append(mem)

        # 4. Create Chores
        chore_specs = [
            {
                "title": "Wash Dishes & Clean Sink",
                "description": "Wash cooking pans, load/unload dishwasher, wipe down countertops and sink basin.",
                "effort_level": Chore.EFFORT_SMALL,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 1, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_SPECIFIC,
                "deadline_window_hours": 24,
            },
            {
                "title": "Take Out Recycling & Trash",
                "description": "Empty kitchen, bathroom, and office bins into curb cans. Roll bins to curb on collection day.",
                "effort_level": Chore.EFFORT_SMALL,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 3, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_SPECIFIC,
                "deadline_window_hours": 48,
            },
            {
                "title": "Vacuum Living Room & Hallway",
                "description": "Vacuum high-traffic carpets, rugs, and under the coffee table.",
                "effort_level": Chore.EFFORT_MEDIUM,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 7, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_SPECIFIC,
                "deadline_window_hours": 72,
            },
            {
                "title": "Mop Kitchen & Dining Area",
                "description": "Sweep and damp mop kitchen and dining tile floors with disinfectant.",
                "effort_level": Chore.EFFORT_MEDIUM,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 7, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_SPECIFIC,
                "deadline_window_hours": 72,
            },
            {
                "title": "Deep Clean Bathroom & Shower",
                "description": "Scrub toilet, disinfect bathtub tiles, clean mirror, and wash floor mats.",
                "effort_level": Chore.EFFORT_LARGE,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 7, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_SPECIFIC,
                "deadline_window_hours": 96,
            },
            {
                "title": "Wipe Down Appliances & Microwave",
                "description": "Clean interior microwave splatters, degrease stovetop hood, and sanitize fridge handles.",
                "effort_level": Chore.EFFORT_LARGE,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 14, "unit": "days"},
                "deadline_mode": Chore.DEADLINE_FLEXIBLE_WINDOW,
                "deadline_window_hours": 168,
            },
        ]

        chores = []
        for spec in chore_specs:
            chore, _ = Chore.objects.get_or_create(
                household=household,
                title=spec["title"],
                defaults=spec,
            )
            chores.append(chore)

        # 5. Seed 8 Weeks of Historical Occurrences & Activity
        now = timezone.now()
        assignee_cycle = [alice, bob, charlie, dana]

        # Reset streaks first so history cleanly builds realistic streak stats
        for u in users:
            streak = StatsService.get_or_create_streak(u)
            streak.current_streak = 0
            streak.longest_streak = 0
            streak.save()

        history_count = 0
        for week_idx in range(8, 0, -1):
            week_start = now - timedelta(weeks=week_idx)

            for chore_idx, chore in enumerate(chores):
                scheduled_time = week_start + timedelta(days=chore_idx)
                due_time = scheduled_time + timedelta(hours=chore.deadline_window_hours or 48)

                assignee = assignee_cycle[(week_idx + chore_idx) % len(assignee_cycle)]

                # Determine outcome
                # 80% on-time completion, 10% late completion, 10% missed
                is_missed = (week_idx == 6 and chore_idx == 0) or (week_idx == 3 and chore_idx == 2)
                is_late = (week_idx == 4 and chore_idx == 1) or (week_idx == 2 and chore_idx == 3)

                if is_missed:
                    status = ChoreOccurrence.STATUS_MISSED
                    comp_time = None
                    missed_time = due_time
                elif is_late:
                    status = ChoreOccurrence.STATUS_COMPLETED_LATE
                    comp_time = due_time + timedelta(hours=6)
                    missed_time = due_time
                else:
                    status = ChoreOccurrence.STATUS_COMPLETED
                    comp_time = scheduled_time + timedelta(hours=12)
                    missed_time = None

                occ = ChoreOccurrence.objects.create(
                    chore=chore,
                    status=status,
                    scheduled_start=scheduled_time,
                    due_date=due_time,
                    completed_at=comp_time,
                    missed_at=missed_time,
                    was_missed=bool(missed_time),
                )

                # Verification on some completed chores
                if status == ChoreOccurrence.STATUS_COMPLETED and week_idx % 2 == 0:
                    verifier = bob if assignee == alice else alice
                    occ.is_verified = True
                    occ.verified_by = verifier
                    occ.verified_at = comp_time + timedelta(hours=2)
                    occ.verification_notes = "Inspected and confirmed done properly."
                    occ.save()

                # Chore assignment
                assignment = ChoreAssignment.objects.create(
                    occurrence=occ,
                    user=assignee,
                    completed=bool(comp_time),
                    completed_at=comp_time,
                    was_missed=bool(missed_time),
                    missed_at=missed_time,
                    notes="Completed on schedule." if status == ChoreOccurrence.STATUS_COMPLETED else "",
                )

                # Update stats & logs
                if status == ChoreOccurrence.STATUS_COMPLETED:
                    StatsService.record_on_time_completion(assignee)
                    ActivityService.log_event(
                        household=household,
                        actor=assignee,
                        event_type=ActivityLog.EVENT_CHORE_COMPLETED,
                        chore=chore,
                        occurrence=occ,
                        title=f"{assignee.display_name} completed {chore.title}",
                        description=f"{assignee.display_name} completed '{chore.title}' on time.",
                    )
                elif status == ChoreOccurrence.STATUS_COMPLETED_LATE:
                    StatsService.record_late_completion(assignee)
                    ActivityService.log_event(
                        household=household,
                        actor=assignee,
                        event_type=ActivityLog.EVENT_CHORE_COMPLETED_LATE,
                        chore=chore,
                        occurrence=occ,
                        title=f"{assignee.display_name} completed {chore.title} late",
                        description=f"{assignee.display_name} completed '{chore.title}' past deadline.",
                    )
                elif status == ChoreOccurrence.STATUS_MISSED:
                    StatsService.record_missed_chore(assignee)
                    ActivityService.log_event(
                        household=household,
                        actor=assignee,
                        event_type=ActivityLog.EVENT_CHORE_MISSED,
                        chore=chore,
                        occurrence=occ,
                        title=f"{chore.title} missed by {assignee.display_name}",
                        description=f"{assignee.display_name} missed deadline for '{chore.title}'.",
                    )

                history_count += 1

        # 6. Create Current Active Occurrences
        active_occurrences = []
        for chore_idx, chore in enumerate(chores):
            assignee = assignee_cycle[chore_idx % len(assignee_cycle)]
            scheduled_time = now - timedelta(hours=chore_idx * 4)
            due_time = scheduled_time + timedelta(hours=chore.deadline_window_hours or 48)

            occ = ChoreOccurrence.objects.create(
                chore=chore,
                status=ChoreOccurrence.STATUS_ACTIVE,
                scheduled_start=scheduled_time,
                due_date=due_time,
            )
            ChoreAssignment.objects.create(
                occurrence=occ,
                user=assignee,
                completed=False,
            )
            active_occurrences.append(occ)

        # 7. Seed Anonymous Chore Suggestions
        suggestions_data = [
            {
                "title": "Organize Pantry & Spice Rack",
                "description": "Sort pantry shelves by item category, group spices, and toss expired items.",
                "effort_level": Chore.EFFORT_SMALL,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 30, "unit": "days"},
                "status": ChoreSuggestion.STATUS_PENDING,
                "approvers": [alice, bob],
                "rejecters": [],
            },
            {
                "title": "Clean Under Living Room Couch",
                "description": "Pull out sectional sofa, vacuum accumulated dust and lost items.",
                "effort_level": Chore.EFFORT_MEDIUM,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 14, "unit": "days"},
                "status": ChoreSuggestion.STATUS_PENDING,
                "approvers": [dana],
                "rejecters": [bob],
            },
            {
                "title": "Quarterly Balcony Power Wash",
                "description": "Hose down balcony concrete, sweep cobwebs, and clean outdoor chairs.",
                "effort_level": Chore.EFFORT_LARGE,
                "recurrence_type": Chore.RECURRENCE_INTERVAL,
                "recurrence_rule": {"interval": 90, "unit": "days"},
                "status": ChoreSuggestion.STATUS_PENDING,
                "approvers": [charlie],
                "rejecters": [],
            },
        ]

        for s_data in suggestions_data:
            sug, _ = ChoreSuggestion.objects.get_or_create(
                household=household,
                title=s_data["title"],
                defaults={
                    "description": s_data["description"],
                    "effort_level": s_data["effort_level"],
                    "recurrence_type": s_data["recurrence_type"],
                    "recurrence_rule": s_data["recurrence_rule"],
                    "status": s_data["status"],
                    "creator": alice,
                },
            )
            for voter in s_data["approvers"]:
                ChoreSuggestionVote.objects.get_or_create(
                    suggestion=sug,
                    voter=voter,
                    defaults={"approved": True},
                )
            for voter in s_data["rejecters"]:
                ChoreSuggestionVote.objects.get_or_create(
                    suggestion=sug,
                    voter=voter,
                    defaults={"approved": False},
                )

        # 8. Seed Chore Swap Request
        # Bob proposes to swap his active chore with Charlie
        bob_occ = next((o for o in active_occurrences if o.assignments.filter(user=bob).exists()), active_occurrences[0])
        charlie_occ = next((o for o in active_occurrences if o.assignments.filter(user=charlie).exists()), active_occurrences[1])

        swap_req, _ = ChoreSwapRequest.objects.get_or_create(
            household=household,
            proposer=bob,
            proposer_occurrence=bob_occ,
            recipient=charlie,
            defaults={
                "recipient_occurrence": charlie_occ,
                "status": ChoreSwapRequest.STATUS_PENDING,
                "notes": "Studying for midterm exam on Thursday, will take your next weekend turn!",
            },
        )

        ActivityService.log_event(
            household=household,
            actor=bob,
            event_type=ActivityLog.EVENT_CHORE_SWAP_ACCEPTED,
            title=f"Chore swap accepted between {bob.display_name} and {charlie.display_name}",
            description=f"{bob.display_name} and {charlie.display_name} exchanged chore duties.",
        )

        # 9. Seed Approved Absence Request
        absence_start = (now + timedelta(days=14)).date()
        absence_end = (now + timedelta(days=21)).date()

        dana_member = next(m for m in members if m.user == dana)
        absence_req, _ = AbsenceRequest.objects.get_or_create(
            household=household,
            member=dana_member,
            defaults={
                "start_date": absence_start,
                "end_date": absence_end,
                "reason": "Annual family reunion camping trip",
                "status": AbsenceRequest.STATUS_APPROVED,
            },
        )
        for voter in [alice, bob, charlie]:
            AbsenceRequestVote.objects.get_or_create(
                absence_request=absence_req,
                voter=voter,
                defaults={"approved": True},
            )

        ActivityService.log_event(
            household=household,
            actor=dana,
            event_type=ActivityLog.EVENT_MEMBER_ABSENCE_APPROVED,
            title=f"Absence approved for {dana.display_name}",
            description=f"{dana.display_name} will be away from {absence_start} to {absence_end}.",
        )

        # 10. Summary Report
        self.stdout.write(self.style.SUCCESS("[OK] Demo Household Seeded Successfully!"))
        self.stdout.write(f"Household: {household.name} (Invite Code: {household.invite_code})")
        self.stdout.write("Roommates:")
        for u in users:
            streak = StatsService.get_or_create_streak(u)
            self.stdout.write(f"  * {u.display_name} ({u.email}) [Password: Pass1234!] - Streak: {streak.current_streak} (Best: {streak.longest_streak})")
        self.stdout.write(f"Chores: {len(chores)} active recurring chores")
        self.stdout.write(f"History: {history_count} occurrences across 8 weeks")
        self.stdout.write(f"Active Occurrences: {len(active_occurrences)} current tasks")
        self.stdout.write(f"Suggestions: {len(suggestions_data)} proposals with votes")
        self.stdout.write(f"Pending Swaps: 1 ({bob.display_name} <-> {charlie.display_name})")
        self.stdout.write(f"Absences: 1 approved ({dana.display_name} for {absence_start} to {absence_end})")
