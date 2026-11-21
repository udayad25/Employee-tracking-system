#!/usr/bin/env python
"""Command-line utility for Django administrative tasks."""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "emts_project.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as error:
        raise ImportError(
            "Django is not installed. Activate your virtual environment and "
            "run: pip install -r requirements.txt"
        ) from error

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
