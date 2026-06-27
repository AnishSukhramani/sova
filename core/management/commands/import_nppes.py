"""
Management command for the initial NPPES practice import.

Usage:
    docker compose exec web python manage.py import_nppes
    docker compose exec web python manage.py import_nppes --file /app/data/nppes_data.csv

Runs the nppes_collector Celery task synchronously (no broker round-trip) via
.apply(). The SovaBaseTask lifecycle still fires, so SubFragmentRunLog records
the run.
"""

from django.core.management.base import BaseCommand

from collectors.tasks.practice_data import nppes_collector


class Command(BaseCommand):
    help = 'Import dental practices from the NPPES monthly CSV (streams the file).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='/app/data/nppes_data.csv',
            help='Path to the NPPES CSV file inside the container.',
        )

    def handle(self, *args, **options):
        csv_path = options['file']
        self.stdout.write(f'Starting NPPES import from {csv_path}')
        result = nppes_collector.apply(args=[csv_path])
        if result.successful():
            count = result.result or 0
            self.stdout.write(self.style.SUCCESS(f'Done. {count} practices written.'))
        else:
            self.stdout.write(self.style.ERROR(f'Import failed:\n{result.traceback}'))
