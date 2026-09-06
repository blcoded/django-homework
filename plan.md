# Shared Household Chores — V1 Product Scope

## 1. Product concept
A shared household operating system for **roommates / shared apartments**, with **chores as the core V1 experience**.

The product should make chores feel less burdensome by automating fair assignment, keeping future assignments somewhat anonymous/surprising, and providing lightweight stats and household history.

## 2. V1 scope
### In scope
- Household creation and membership
- Chore creation, editing, removal
- One-off chores
- Recurring chores
- Optional chore deadlines
- Specific or flexible deadline windows
- Automatic fair chore distribution
- Workload balancing using Small / Medium / Large effort levels
- Rotation over time
- 8-week recent completed-work history for fairness
- Upcoming, Active, Completed, Missed, and Disputed states
- Early "You're next" notifications
- Active chore reminders
- One-tap completion
- Optional completion notes/photos
- Optional roommate verification
- Completion disputes that remain in history
- Missed-chore tracking and late-completion stats
- Chore swaps requiring both roommates to accept
- Temporary rotation pauses with whole-household approval
- Automatic rebalancing during pauses
- Immediate return to rotation when a roommate returns
- Household member join/leave handling
- Shared household activity feed
- Personal and household-visible chore history/stats
- Lightweight stats/streaks/milestones; no leaderboard

### Out of scope for V1
- Shared expenses
- Household supplies/inventory
- Expense settlement/balances
- Competitive leaderboards
- Full future rotation visibility

## 3. Household model
- Target: roommates / shared apartments.
- One roommate starts a household.
- Others join through an invite link/code.
- Household-wide approval can be required for joining.
- **All roommates have equal permissions**; there is no household admin/boss role.

## 4. Chore creation
Anyone can **suggest** a chore.

Suggested chores:
- Are anonymous.
- Require **majority household approval** before entering the active chore system.
- Expire after a fixed period if nobody approves or rejects them.

Once approved, a chore can be:
- **One-off** — happens once.
- **Recurring** — repeats on a chosen schedule.

Chores can be added, edited, or removed.

## 5. Chore timing and deadlines
A chore has two distinct concepts:

### Schedule
When an occurrence is expected to happen / recur.

### Deadline
An optional point or window by which it should be completed.

The household/creator chooses the deadline behavior when the chore is added:
- No deadline
- Specific deadline
- Flexible window (for example, "this weekend")

Recurring chores normally retain the same effort level each occurrence.

## 6. Assignment lifecycle
A roommate can encounter a chore in these broad states:

1. **Upcoming** — assigned to them for a future occurrence, not actionable yet.
2. **Active** — their action window has started.
3. **Completed** — completed normally.
4. **Missed** — deadline passed without completion.
5. **Completed late** — a missed chore later completed.
6. **Disputed** — completion is challenged but remains in the record.

### Assignment timing
Default behavior should allow the system to assign a chore **a few hours before it becomes due/active**, giving the roommate time to plan.

For recurring chores, the system may also assign the **next person immediately after the previous occurrence is completed**, so the next roommate knows they are next.

The product should distinguish:
- **Next up:** responsibility is known in advance.
- **Active:** action is currently expected.
- **Overdue/Missed:** deadline has passed.

## 7. Fairness and rotation
Automatic distribution is a core product feature.

Fairness is based on:
- Balanced workload rather than simply counting chores.
- Rotation so roommates eventually experience different chore types.
- Each chore having an effort level: **Small / Medium / Large**.
- The app suggests the effort level; the creator can edit it.

### Fairness history
- Use the most recent **8 weeks** of history.
- Only **completed chores** count toward the fairness workload history.
- A completed-late chore counts normally toward workload.
- Missed chores do **not** count toward fairness workload, but remain tracked separately as performance history.
- Old history gradually loses influence by falling outside the 8-week window.

There are **no manual minimum/maximum chore quotas** per roommate.

A visible fairness score is intentionally excluded. Fairness should work behind the scenes.

## 8. Upcoming visibility and surprise element
- Upcoming assignments are visible to the household, but only the **next upcoming assignment** should be shown.
- Do **not** expose the full future rotation.
- The goal is to keep some uncertainty and fun around who is next.
- The exact visibility behavior for upcoming assignments can be configured so the household may hide them until active, while the product default should support the "everyone can see what is next" concept.

## 9. Notifications
Two key notification moments:

### Early notification
**"You're next"** — gives the roommate advance notice and lets them plan.

### Active reminder
**"It's your turn"** — tells the roommate the chore is now active and requires action.

For V1, notification behavior is controlled by a **household-wide notification policy** rather than individual roommate preferences. The two core notification moments are: early “You're next” and active “It's your turn.”

## 10. Completion
Default flow:
- Tap **Complete**.

Optional additions:
- Completion note
- Photo/evidence

### Verification
- Roommate verification is optional at the household level.
- If verification is enabled, a roommate can verify a completion.
- A disputed completion remains recorded as completed and is marked **Disputed**; the app does not silently erase completion history.

## 11. Missed and late chores
A missed chore remains attached to the originally assigned person.

When a chore is missed:
- It is recorded as a missed chore.
- It contributes to the person's missed-chore statistics.
- It should not silently disappear or be reassigned as if nothing happened.

When a missed chore is later completed:
- Mark it as **Completed late**.
- Preserve the missed history.
- Count the completed chore normally in workload fairness.
- Track late completion separately in stats.

The product should support statistics such as:
- Total missed chores
- Missed chores later completed
- Late completions
- On-time completions

## 12. Chore swaps
- Roommates may swap chores.
- A swap only takes effect when **both roommates accept** it.
- Swaps are treated as favors.
- Swaps **do not change the underlying fairness calculation**.

## 13. Temporary absence / pause
A roommate can temporarily pause participation without leaving the household, for situations such as travel or unavailability.

Rules:
- Requires **approval from the entire household**.
- Supports preset durations and custom duration.
- A paused roommate is **completely excluded from new chore assignments**.
- Existing/future eligible assignments should be recalculated automatically.
- The system automatically rebalances chores among remaining available roommates.

When the roommate returns:
- They rejoin immediately.
- They enter the **next available rotation**, meaning only chores that have not already been assigned/activated for someone else.

## 14. Joining a household
A new roommate:
- Enters the chore rotation immediately.
- Only enters **next available** chore occurrences.
- Does not take over a chore that is already active.

## 15. Leaving a household
Leaving requires **whole-household approval**.

When someone leaves:
- Remove them from future rotation.
- Reassign their active chores automatically.
- Rebalance the affected workload.

## 16. When fair assignment is impossible
If there are not enough eligible roommates to fairly assign an active chore:
- Leave the chore **unassigned**.
- Flag/notify the household so it can be resolved.

Do not silently force an unfair assignment.

## 17. Home screen
The home screen should remain **chore-focused**.

Primary section:
- **My Chores**
  - Active chores
  - Next/upcoming chore
  - Relevant reminders/statuses

Secondary section:
- **Household Overview**
  - Current household chore status
  - Relevant recent activity

Expenses and supplies should not appear on the home screen because they are out of V1 scope.

## 18. Activity and stats
A shared household activity feed should show events such as:
- Chore completed
- Chore missed
- Chore completed late
- Chore disputed
- Chore assigned/swapped as appropriate

History and stats are **fully visible to all roommates**.

Light gamification is included:
- Personal streaks
- Milestones / achievements
- Simple stats

No competitive leaderboard.

## 19. Core product principle
The system should feel **fair, automatic, transparent, and lightweight** rather than bureaucratic.

Important UX principles:
- Automate fairness instead of making roommates negotiate assignments.
- Keep future rotation partially hidden to create a small element of surprise.
- Make active responsibilities obvious.
- Preserve history rather than rewriting it.
- Treat swaps and temporary absences as explicit exceptions to the normal rotation.
- Keep the experience centered on chores in V1.

## 20. Final decisions from the brainstorming session

- Recurring schedules support both fixed calendar schedules and interval-based recurrence; the chore creator chooses which model to use.
- Chores are single-person by default, but a chore can optionally require multiple roommates.
- Multi-person chores require **every assigned roommate** to mark the chore complete.
- The entire household can pause the chore system temporarily.
- Household-wide pauses cause occurrences during the pause to be **ignored completely**; they are not marked missed and do not affect fairness.
- Notification behavior uses a **single household-wide policy** in V1 rather than per-roommate customization.

## 21. Decisions still open
The following details were intentionally not fully specified yet and should be resolved during detailed product/technical design rather than through endless scope questions:

- Exact default timing for "a few hours before" a chore becomes active.
- Exact recurring schedule options and timezone handling.
- Exact rules for calculating Small / Medium / Large workload values.
- Exact majority calculation for households with an even number of roommates.
- Exact suggestion expiration duration.
- Exact approval mechanics and notifications.
- Exact notification preference controls.
- Whether upcoming chores are visible by default until activation or only to the assigned person.
- Exact algorithm for breaking workload ties.
- Edge-case behavior when a household has only one eligible roommate.

## 22. Suggested V1 navigation
A simple structure could be:

- **Home** — My Chores + Household Overview
- **Chores** — all active/upcoming/completed chores
- **Activity** — household activity/history
- **Stats** — visible household/person stats and streaks
- **Household** — members, approvals, pause/leave requests, household settings
- **Profile/Settings** — personal notifications and preferences

## 23. Example recurring chore
**Chore:** Pay NEPA bill

- Type: Recurring
- Frequency: Weekly
- Deadline: Friday, 8:00 PM
- Effort: Small
- Assignment: current roommate is responsible for the current occurrence
- Next roommate may be informed immediately after the current occurrence is completed
- The next roommate sees that they are **next**, but the full future rotation remains hidden
- A few hours before the deadline, the chore becomes **Active** and the roommate receives the active reminder

## 24. Product definition in one sentence
**A roommate-focused household app that automatically and fairly rotates chores, handles availability and exceptions, tracks completion history, and keeps the experience lightweight and a little fun.**

## 25. Recommended technology stack
Django is a compulsory part of the stack. The recommended architecture keeps Django responsible for the core business logic and fairness rules while using a modern frontend for the user experience.

### Backend
- **Django** — core backend and business logic
- **Django REST Framework (DRF)** — API layer
- **PostgreSQL** — primary relational database
- **Celery + Redis** — scheduled/background jobs such as recurring chore generation, reminders, and notifications; introduce when these workloads justify it
- **Django Channels** — optional real-time updates for household activity; not required for the initial MVP

### Frontend
- **Next.js** — web application framework
- **TypeScript** — type safety and maintainability
- **Tailwind CSS** — styling
- **shadcn/ui** — reusable UI components

### Authentication
- Start with **Django authentication/session-based auth** for the web application.
- **django-allauth** can be added for email and social authentication.
- Avoid introducing JWT unless a separate mobile client or other independent API consumers require it.

### Notifications
- **In-app notifications** stored in PostgreSQL
- **Email:** Resend or SendGrid
- **Push notifications:** Firebase Cloud Messaging when mobile/push support is added

### Deployment
A practical deployment setup:
- **Django:** Render, Railway, or Fly.io
- **PostgreSQL:** managed PostgreSQL from the deployment provider or Neon
- **Redis:** Upstash Redis
- **Next.js:** Vercel

### Recommended V1 architecture
For the first implementation, keep the stack deliberately small:

**Next.js + TypeScript + Tailwind + shadcn/ui**
→ **Django + Django REST Framework**
→ **PostgreSQL**

Add **Redis/Celery** when recurring scheduling and notification workloads become substantial. Add **Django Channels** only if real-time functionality becomes a meaningful product requirement.

### Responsibility boundaries
The frontend should handle presentation and user interaction, while Django owns the authoritative household rules and business logic, including:
- Chore scheduling
- Recurring occurrence generation
- Assignment and rotation
- Fairness calculations
- Effort/load balancing
- Pause and rejoin logic
- Chore swaps
- Missed and late-completion state changes
- Verification/dispute workflows
- Household membership rules
- Notification triggers

The fairness algorithm should **not** live in the frontend. Keeping it in Django ensures that assignments are consistent, testable, and enforceable regardless of client.

### Overall recommendation
**Django + Django REST Framework + PostgreSQL + Next.js + TypeScript + Tailwind CSS + shadcn/ui** is the recommended core stack for this product.
