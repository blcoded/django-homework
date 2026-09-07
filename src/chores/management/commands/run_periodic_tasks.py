from django.core.management.base import BaseCommand
from chores.tasks import (
    run_all_periodic_tasks,
    check_and_activate_occurrences,
    check_and_transition_missed_occurrences,
    dispatch_scheduled_reminders,
)


class Command(BaseCommand):
    help = (
        "Execute scheduled background routines synchronously "
        "(activation checks, deadline evaluations, and reminder dispatches)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-activate",
            action="store_true",
            help="Run only upcoming occurrence activation checks.",
        )
        parser.add_argument(
            "--only-missed",
            action="store_true",
            help="Run only missed occurrence deadline evaluations.",
        )
        parser.add_argument(
            "--only-reminders",
            action="store_true",
            help="Run only reminder notification dispatches.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Starting periodic task execution...")

        if options["only_activate"]:
            activated = check_and_activate_occurrences()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully activated {len(activated)} occurrences.")
            )
            return

        if options["only_missed"]:
            missed = check_and_transition_missed_occurrences()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully transitioned {len(missed)} occurrences to missed.")
            )
            return

        if options["only_reminders"]:
            reminders = dispatch_scheduled_reminders()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully dispatched reminders for {len(reminders)} occurrences.")
            )
            return

        result = run_all_periodic_tasks()
        self.stdout.write(
            self.style.SUCCESS(
                f"Periodic tasks completed successfully: "
                f"{len(result['activated'])} activated, "
                f"{len(result['missed'])} missed, "
                f"{len(result['reminders'])} reminders dispatched."
            )
        )
