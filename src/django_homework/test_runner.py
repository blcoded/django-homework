from django.apps import apps
from django.test.runner import DiscoverRunner


class HomeworkTestRunner(DiscoverRunner):
    """
    Custom test runner that discovers tests in project apps
    when no test labels are provided on the command line.
    """

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if not test_labels:
            test_labels = [
                app_config.label
                for app_config in apps.get_app_configs()
                if not app_config.name.startswith("django.")
                and app_config.name not in ("rest_framework", "corsheaders")
            ]
            from django.conf import settings
            if (settings.BASE_DIR / "tests").is_dir():
                test_labels.append("tests")
        return super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)

