from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.test.runner import DiscoverRunner


class HomeworkTestRunner(DiscoverRunner):
    """
    Custom test runner that discovers tests in project apps and root tests/
    when no test labels are provided on the command line.
    """

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if not test_labels:
            base_dir = Path(settings.BASE_DIR).resolve()
            test_labels = []
            for app_config in apps.get_app_configs():
                app_path = Path(app_config.path).resolve()
                if (
                    base_dir in app_path.parents
                    and not app_config.name.startswith("django.")
                ):
                    test_labels.append(app_config.name)

            if (base_dir / "tests").is_dir():
                test_labels.append("tests")
        return super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)
