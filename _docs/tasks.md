# Product Backlog: Shared Household Chores (V1)

## 1. Setting Up an Empty Project with a Passing Test
Goal: Initialize the Django project environment and configure a baseline test runner with a passing smoke test.
Description: Configure the project dependencies with uv including Django, Django REST Framework, and development testing utilities. Initialize the standard Django project directory structure with a settings configuration that supports local development. Create an initial automated test case that runs through the Django test runner and passes successfully.

## 2. User Authentication, Custom Model, and Registration
Goal: Implement a custom user model and complete authentication workflows including registration, login, logout, and profile retrieval.
Description: Create a custom User model extending Django's AbstractUser to support email-based authentication and display names. Build secure registration, login, logout, and current user profile API endpoints with serializer validation. Include automated tests verifying credential validation, token or session handling, and duplicate email rejection.

## 3. Household Management and Equal Permissions Model
Goal: Create models and endpoints for creating households, generating invite links, and managing members with equal permissions.
Description: Implement Household and HouseholdMember models storing timezone settings, configuration flags, and member statuses without any admin or boss roles. Build endpoints allowing authenticated users to create a household, automatically enroll as the first active member, and generate secure invite codes for prospective roommates. Add unit tests ensuring all active members have equal permissions and that invite codes are unique.

## 4. Household Membership Approval Workflows (Join and Leave)
Goal: Implement voting-based workflows for joining a household with approval and leaving a household with whole-household consent.
Description: Create request and voting models for prospective roommates requesting to join and existing roommates requesting to leave the household. Enforce household-wide approval rules where either optional join approval or mandatory departure approval requires unanimous consent from all active members. Write integration tests verifying that member state transitions only take effect once all required roommate votes are cast.

## 5. Chore Definition Model with Recurrence, Deadlines, and Multi-Assignee Support
Goal: Define the core Chore model supporting one-off and recurring schedules, effort ratings, flexible deadlines, and multi-person assignments.
Description: Build a Chore model with fields for title, description, effort rating (Small, Medium, Large), recurrence type (calendar or interval), and deadline modes (none, specific, or flexible window). Include support for multi-person chores requiring every assigned roommate to independently complete the chore. Write model tests validating schedule rule serialization, deadline calculations, and multi-assignee validation constraints.

## 6. Chore Management CRUD Endpoints with Effort Level Heuristic
Goal: Provide REST endpoints for managing household chores alongside an automated effort level suggestion helper.
Description: Build Django REST Framework endpoints for listing, viewing, updating, and archiving household chores scoped strictly to the authenticated user's household. Integrate a lightweight heuristic helper that analyzes chore titles to suggest Small, Medium, or Large effort levels while allowing creator overrides. Include integration tests verifying permission scoping, chore updates, soft deletion, and effort suggestion accuracy.

## 7. Anonymous Chore Suggestion and Majority Voting Lifecycle
Goal: Implement an anonymous chore suggestion pipeline with majority household voting and automatic expiration.
Description: Create ChoreSuggestion and voting models allowing active roommates to propose chores without exposing the creator's identity. Implement majority vote threshold logic that automatically converts approved suggestions into active chores, alongside an expiration check that archives unreviewed proposals after a fixed duration. Write unit tests confirming creator anonymity, majority vote calculations, and automatic expiration handling.

## 8. Chore Occurrence Lifecycle and Activation Service
Goal: Define occurrence models and implement automated occurrence generation and activation services.
Description: Create ChoreOccurrence and ChoreAssignment models tracking states including Upcoming, Active, Completed, Missed, Completed Late, and Disputed. Implement services that generate the next single occurrence for recurring chores upon completion and automatically transition upcoming chores to active when their action window opens. Add unit tests asserting accurate state transitions and verifying that only one upcoming occurrence exists per recurring chore.

## 9. Authoritative Fair Assignment Engine
Goal: Implement the core assignment algorithm balancing 8-week completed workload, chore variety, and deterministic tie-breaking.
Description: Build a backend assignment engine that queries each active roommate's completed chore points over the trailing 56 days, strictly excluding missed chores from workload credit. Incorporate chore variety scoring to prevent repetitive chore assignments and apply deterministic tie-breaking among eligible active roommates. Write extensive simulation and unit tests verifying long-term workload balance and resilience across different household sizes.

## 10. Single Next-Up Visibility and Hidden Rotation Service
Goal: Expose only the immediate next upcoming chore assignee while keeping future rotation secret.
Description: Build a service ensuring that the API exposes only the single next upcoming occurrence and its assigned roommate for each chore. Prevent the database or endpoints from generating or leaking multi-week future schedules to preserve the element of surprise. Write tests asserting that client responses only contain the immediate next assignee and never disclose future rotation order.

## 11. Missed Chore Detection and Late Completion Handling
Goal: Automatically detect past-due active chores and support completing missed chores with workload credit.
Description: Build a service that transitions past-due active occurrences to Missed while keeping them assigned to the responsible roommate and recording missed statistics. Implement late completion logic that transitions missed chores to Completed Late, preserving the missed record while crediting the effort points toward the roommate's 8-week fairness workload. Add unit tests validating automatic missed transitions and proper workload crediting for late completions.

## 12. Chore Completion Workflow with Proof Upload and Multi-Person Support
Goal: Implement chore completion endpoints supporting optional notes, photo evidence uploads, and multi-person coordination.
Description: Create completion API endpoints allowing roommates to mark chores completed with optional notes and validated image photo proof. Enforce completion gating for multi-person chores such that the occurrence only completes once every assigned roommate submits their completion. Write unit and integration tests verifying single-tap completion, photo upload handling, and multi-assignee completion requirements.

## 13. Household Completion Verification and Dispute Workflows
Goal: Support optional roommate completion verification and an audit-preserving dispute mechanism.
Description: Add an optional household verification toggle enabling roommates to formally verify completed chores. Implement a dispute endpoint that flags an occurrence as Disputed with an explanation note without erasing the underlying completion record, timestamps, or proof. Write unit tests ensuring verification can be recorded and confirming that disputed chores retain full historical integrity.

## 14. Chore Swap Request and Mutual Acceptance Workflow
Goal: Enable roommates to swap chore assignments requiring mutual acceptance without altering fairness scores.
Description: Build a ChoreSwapRequest model and endpoints allowing a roommate to propose an occurrence swap to another roommate who must explicitly accept or decline. Upon mutual agreement, swap the assigned roommates on the respective occurrences while treating the exchange as a personal favor that leaves 8-week fairness calculations unaffected. Write tests verifying mutual acceptance enforcement and confirming that fairness history remains unaltered.

## 15. Member Temporary Absence Lifecycle and Automated Rebalancing
Goal: Manage temporary member pauses with household approval, automatic chore rebalancing, and seamless return to rotation.
Description: Implement an absence request workflow requiring unanimous household approval to place a roommate into a paused status for preset or custom dates. Automatically rebalance and reassign the paused member's pending chores among available roommates, and reintegrate returning members into the next available rotation without displacing active chores. Add unit tests covering pause approval, automated chore redistribution, and immediate re-entry into rotation.

## 16. Household Pauses, Member Departures, and Unassigned Fallback
Goal: Handle household-wide chore freezes, departing member chore reassignments, and alerts when fair assignment is impossible.
Description: Build services to freeze all chore activity during household-wide pauses without missed penalties, and reassign active chores when a member departure is approved. Implement fallback logic that marks an occurrence as Unassigned and generates a household alert when zero eligible roommates are available for assignment. Write integration tests testing pause suspension, departure workload rebalancing, and unassigned state alerts.

## 17. In-App and Email Notification System with Core Dispatch Moments
Goal: Build the notification engine delivering "You're next" advance alerts and "It's your turn" active reminders.
Description: Implement a Notification model with read-tracking endpoints and an email dispatch adapter supporting both development console logging and production delivery. Create dispatch triggers for the two core V1 household notification moments: early "You're next" warnings upon assignment and active "It's your turn" alerts upon window activation. Write tests checking notification creation, read status updates, email formatting, and delivery trigger timing.

## 18. Scheduled Background Worker and Periodic Runner Setup
Goal: Configure Celery and periodic scheduled tasks for automated state transitions and reminders.
Description: Set up Celery and Celery Beat backed by Redis to execute recurring tasks including activation checks, deadline evaluations, and notification dispatches. Provide a fallback Django management command to execute all periodic routines synchronously during local development and testing. Write tests verifying that management routines execute cleanly and trigger appropriate occurrence state updates.

## 19. Household Shared Activity Feed and Filterable History Archive
Goal: Create a centralized activity log and a filterable historical archive of all household chore events.
Description: Define an ActivityLog model and API endpoint that streams chore completions, misses, late recoveries, disputes, swaps, and member status changes to all roommates. Build a filterable history endpoint allowing roommates to review past occurrences by date range, specific chore, assignee, and completion status. Write integration tests asserting automatic activity logging and validating historical search filters.

## 20. Personal Streaks, Milestones, and Non-Competitive Statistics
Goal: Compute chore completion performance metrics and manage personal streaks and milestone achievements.
Description: Implement statistics services calculating on-time completions, total misses, late completions, and completion rates while strictly avoiding competitive leaderboards. Track personal consecutive on-time streaks that reset upon missed chores and award milestone achievement badges for personal consistency. Write unit tests validating metric calculations, streak increment/reset rules, and milestone unlock conditions.

## 21. Next.js Application Shell, Navigation, and Theme Setup
Goal: Initialize the Next.js 14+ frontend with TypeScript, Tailwind CSS, shadcn/ui, and a responsive navigation shell.
Description: Configure the Next.js App Router project with Tailwind CSS, theme styling, and base shadcn/ui components including buttons, dialogs, cards, and badges. Build a responsive application shell with a desktop sidebar, mobile drawer, and top navigation linking to Home, Chores, Activity, Stats, and Household views. Write component tests checking that navigation items render properly and highlight active routes.

## 22. Frontend Authentication and Household Onboarding Pages
Goal: Build user authentication forms and household onboarding workflows for creating or joining a household.
Description: Implement user registration and login forms integrated with the backend authentication APIs and session state management. Build household onboarding pages allowing a user to either create a new household or join an existing one using an invite code. Write component tests verifying client-side validation, error handling, and redirection upon successful authentication.

## 23. Frontend Home Dashboard ("My Chores" and "Household Overview")
Goal: Implement the primary home screen combining personal chore cards with a household overview and activity ticker.
Description: Create the "My Chores" section displaying active chore cards with countdowns, next-up cards, overdue alerts, and quick-completion triggers. Build the "Household Overview" section showing overall chore statuses, unassigned alerts, and a compact ticker of recent household activity. Write frontend tests checking component rendering, state displays, and correct chore categorization.

## 24. Frontend Chores Catalog, Completion Modal, and Anonymous Suggestions
Goal: Build the chores catalog view, one-tap completion modal with photo upload, and anonymous chore suggestion dialog.
Description: Develop a chores list with filtering by status and effort level alongside an anonymous chore suggestion dialog with voting controls. Build an interactive completion modal allowing roommates to submit optional completion notes and photo evidence with instant optimistic UI updates. Write component tests testing completion submission, file upload handling, suggestion submission, and voting interactions.

## 25. Frontend Swaps, Absence Requests, Activity Feed, and Dispute Review
Goal: Implement modals for requesting swaps and pauses alongside a chronological activity feed with dispute actions.
Description: Create interactive dialogs for proposing and accepting chore swaps and submitting temporary pause requests to the household. Build a chronological activity feed showing member events, expandable proof images, and interactive buttons to verify completions or open dispute dialogues. Write component tests covering swap proposals, absence form submissions, timeline rendering, and dispute submission.

## 26. Frontend Stats, Milestones, and Household Member Management Views
Goal: Build screens for visualizing personal streaks and stats, managing household members, and configuring policies.
Description: Develop a stats screen displaying personal streaks, unlocked milestone badges, and non-competitive household completion summaries. Build a household settings page displaying member cards, invite link sharing tools, pending approval votes, and toggles for verification and notification policies. Write tests verifying metric visualizations, invite code copy functionality, and household settings updates.

## 27. Household Demonstration Seed Script and End-to-End Test Suite
Goal: Provide a realistic demo seed management command and an automated end-to-end integration test suite.
Description: Implement a Django management command that seeds a sample household with 4 roommates, active and recurring chores, 8 weeks of realistic history, and pending suggestions. Create an end-to-end test suite verifying the complete flow from household creation and assignment through completion, missed detection, swaps, and fair rebalancing. Document command execution and test runner instructions for running the complete demonstration.
