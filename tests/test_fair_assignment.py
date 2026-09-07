from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from chores.assignment import FairAssignmentEngine
from chores.models import Chore, ChoreAssignment, ChoreOccurrence
from chores.services import OccurrenceService
from households.models import Household, HouseholdMember

User = get_user_model()


class FairAssignmentEngineTestCase(TestCase):
    """Unit and simulation tests verifying workload balance, variety scoring, missed exclusion, and resilience."""

    def setUp(self):
        self.household = Household.objects.create(name="Cedar Shared Flat")
        self.user_a = User.objects.create_user(
            email="alice@example.com", password="Password123!", display_name="Alice"
        )
        self.user_b = User.objects.create_user(
            email="bob@example.com", password="Password123!", display_name="Bob"
        )
        self.user_c = User.objects.create_user(
            email="charlie@example.com", password="Password123!", display_name="Charlie"
        )
        self.user_d = User.objects.create_user(
            email="dave@example.com", password="Password123!", display_name="Dave"
        )

        for user in [self.user_a, self.user_b, self.user_c, self.user_d]:
            HouseholdMember.objects.create(
                household=self.household, user=user, status=HouseholdMember.STATUS_ACTIVE
            )

        self.chore_med = Chore.objects.create(
            household=self.household,
            title="Clean Kitchen",
            effort_level=Chore.EFFORT_MEDIUM,  # 2 points
        )
        self.chore_large = Chore.objects.create(
            household=self.household,
            title="Mop Common Areas",
            effort_level=Chore.EFFORT_LARGE,  # 3 points
        )

    def test_trailing_56_days_workload_window(self):
        """Points are strictly counted within trailing 56 days and excluded beyond that window."""
        now = timezone.now()

        # Completed within 56-day window (20 days ago) -> 3 points
        occ1 = ChoreOccurrence.objects.create(
            chore=self.chore_large,
            status=ChoreOccurrence.STATUS_COMPLETED,
            scheduled_start=now - timedelta(days=20),
            completed_at=now - timedelta(days=20),
        )
        ChoreAssignment.objects.create(
            occurrence=occ1, user=self.user_a, completed=True, completed_at=now - timedelta(days=20)
        )

        # Completed outside 56-day window (60 days ago) -> should not count
        occ2 = ChoreOccurrence.objects.create(
            chore=self.chore_large,
            status=ChoreOccurrence.STATUS_COMPLETED,
            scheduled_start=now - timedelta(days=60),
            completed_at=now - timedelta(days=60),
        )
        ChoreAssignment.objects.create(
            occurrence=occ2, user=self.user_a, completed=True, completed_at=now - timedelta(days=60)
        )

        points = FairAssignmentEngine.get_completed_workload_points(
            self.user_a, self.household, current_time=now
        )
        self.assertEqual(points, 3)

    def test_missed_chores_strictly_excluded_from_workload_credit(self):
        """Missed uncompleted chores earn 0 workload credit; late completed chores do earn credit."""
        now = timezone.now()

        # Missed chore (status MISSED, completed=False)
        occ_missed = ChoreOccurrence.objects.create(
            chore=self.chore_large,
            status=ChoreOccurrence.STATUS_MISSED,
            scheduled_start=now - timedelta(days=5),
        )
        ChoreAssignment.objects.create(
            occurrence=occ_missed, user=self.user_a, completed=False
        )

        # Alice has 0 points despite being assigned a large chore
        points_missed = FairAssignmentEngine.get_completed_workload_points(
            self.user_a, self.household, current_time=now
        )
        self.assertEqual(points_missed, 0)

        # Completed Late chore (status COMPLETED_LATE, completed=True)
        occ_late = ChoreOccurrence.objects.create(
            chore=self.chore_med,
            status=ChoreOccurrence.STATUS_COMPLETED_LATE,
            scheduled_start=now - timedelta(days=10),
            completed_at=now - timedelta(days=2),
        )
        ChoreAssignment.objects.create(
            occurrence=occ_late,
            user=self.user_b,
            completed=True,
            completed_at=now - timedelta(days=2),
        )

        points_late = FairAssignmentEngine.get_completed_workload_points(
            self.user_b, self.household, current_time=now
        )
        self.assertEqual(points_late, 2)

    def test_chore_variety_scoring(self):
        """Penalizes assigning the same chore repeatedly to the same roommate."""
        now = timezone.now()

        # Alice and Bob both have equal 2 points overall, but Alice did 'Clean Kitchen'
        occ_alice = ChoreOccurrence.objects.create(
            chore=self.chore_med,  # Clean Kitchen
            status=ChoreOccurrence.STATUS_COMPLETED,
            scheduled_start=now - timedelta(days=3),
            completed_at=now - timedelta(days=3),
        )
        ChoreAssignment.objects.create(
            occurrence=occ_alice, user=self.user_a, completed=True, completed_at=now - timedelta(days=3)
        )

        occ_bob = ChoreOccurrence.objects.create(
            chore=self.chore_large,  # Did Mop instead
            status=ChoreOccurrence.STATUS_COMPLETED,
            scheduled_start=now - timedelta(days=10),
            completed_at=now - timedelta(days=10),
        )
        ChoreAssignment.objects.create(
            occurrence=occ_bob, user=self.user_b, completed=True, completed_at=now - timedelta(days=10)
        )

        # When assigning 'Clean Kitchen' between Alice and Bob, Bob should be favored due to variety
        penalty_alice = FairAssignmentEngine.get_chore_variety_penalty(
            self.user_a, self.chore_med, current_time=now
        )
        penalty_bob = FairAssignmentEngine.get_chore_variety_penalty(
            self.user_b, self.chore_med, current_time=now
        )
        self.assertTrue(penalty_alice > penalty_bob)

    def test_deterministic_tie_breaking(self):
        """Ties are resolved deterministically and stably."""
        # Clean state, all roommates have 0 points
        assignees_1 = FairAssignmentEngine.select_assignees(self.chore_med)
        assignees_2 = FairAssignmentEngine.select_assignees(self.chore_med)

        self.assertEqual(len(assignees_1), 1)
        self.assertEqual(len(assignees_2), 1)
        self.assertEqual(assignees_1[0], assignees_2[0])

    def test_multi_assignee_fair_selection(self):
        """Selects the exact required count of assignees with the lowest workload scores."""
        now = timezone.now()
        # Alice: 5 pts, Bob: 3 pts, Charlie: 2 pts, Dave: 0 pts
        for pts, user in [(5, self.user_a), (3, self.user_b), (2, self.user_c)]:
            ch = Chore.objects.create(
                household=self.household, title=f"Chore {pts}", effort_level=Chore.EFFORT_SMALL
            )
            occ = ChoreOccurrence.objects.create(
                chore=ch, status=ChoreOccurrence.STATUS_COMPLETED,
                scheduled_start=now - timedelta(days=5), completed_at=now - timedelta(days=5)
            )
            ChoreAssignment.objects.create(
                occurrence=occ, user=user, completed=True, completed_at=now - timedelta(days=5)
            )
            # Add remaining dummy points
            if pts > 1:
                ch_extra = Chore.objects.create(
                    household=self.household, title=f"Extra {pts}", effort_level=Chore.EFFORT_LARGE if pts >= 4 else Chore.EFFORT_SMALL
                )
                occ_extra = ChoreOccurrence.objects.create(
                    chore=ch_extra, status=ChoreOccurrence.STATUS_COMPLETED,
                    scheduled_start=now - timedelta(days=4), completed_at=now - timedelta(days=4)
                )
                ChoreAssignment.objects.create(
                    occurrence=occ_extra, user=user, completed=True, completed_at=now - timedelta(days=4)
                )

        multi_chore = Chore.objects.create(
            household=self.household,
            title="Clean Garage Together",
            is_multi_assignee=True,
            required_assignees_count=2,
        )

        selected = FairAssignmentEngine.select_assignees(multi_chore, current_time=now)
        self.assertEqual(len(selected), 2)
        # Dave (0 pts) and Charlie (lowest) should be chosen over Alice and Bob
        self.assertIn(self.user_d, selected)
        self.assertNotIn(self.user_a, selected)

    def test_long_term_simulation_workload_balance(self):
        """Simulate 30 recurring chore cycles among 3 roommates and assert balanced point distribution."""
        sim_household = Household.objects.create(name="Simulation Flat")
        roommates = [
            User.objects.create_user(f"sim_{i}@example.com", "Pass123!", f"Sim {i}")
            for i in range(3)
        ]
        for u in roommates:
            HouseholdMember.objects.create(
                household=sim_household, user=u, status=HouseholdMember.STATUS_ACTIVE
            )

        chores = [
            Chore.objects.create(household=sim_household, title="Dishes", effort_level=Chore.EFFORT_SMALL),
            Chore.objects.create(household=sim_household, title="Vacuum", effort_level=Chore.EFFORT_MEDIUM),
            Chore.objects.create(household=sim_household, title="Bathrooms", effort_level=Chore.EFFORT_LARGE),
        ]

        sim_time = timezone.now() - timedelta(days=40)

        for cycle in range(30):
            chore = chores[cycle % len(chores)]
            assignees = FairAssignmentEngine.select_assignees(chore, current_time=sim_time)
            self.assertEqual(len(assignees), 1)
            assignee = assignees[0]

            occ = ChoreOccurrence.objects.create(
                chore=chore,
                status=ChoreOccurrence.STATUS_COMPLETED,
                scheduled_start=sim_time,
                completed_at=sim_time,
            )
            ChoreAssignment.objects.create(
                occurrence=occ, user=assignee, completed=True, completed_at=sim_time
            )
            sim_time += timedelta(hours=12)

        # Calculate final points
        final_points = [
            FairAssignmentEngine.get_completed_workload_points(u, sim_household, current_time=sim_time)
            for u in roommates
        ]
        max_pts = max(final_points)
        min_pts = min(final_points)

        # Spread between most loaded and least loaded should be at most 3 points (effort rating of 1 large chore)
        self.assertTrue(
            max_pts - min_pts <= 3,
            f"Workload imbalance detected: {final_points}",
        )

    def test_resilience_across_different_household_sizes(self):
        """Engine behaves consistently and safely with 1, 2, and 6 active roommates."""
        for size in [1, 2, 6]:
            h = Household.objects.create(name=f"Size {size} Flat")
            users = [
                User.objects.create_user(f"size_{size}_{i}@example.com", "Pass123!", f"User {i}")
                for i in range(size)
            ]
            for u in users:
                HouseholdMember.objects.create(household=h, user=u, status=HouseholdMember.STATUS_ACTIVE)

            chore = Chore.objects.create(household=h, title="Sweep floor", effort_level=Chore.EFFORT_SMALL)
            selected = FairAssignmentEngine.select_assignees(chore)
            self.assertEqual(len(selected), 1)
            self.assertIn(selected[0], users)
