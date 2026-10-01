from django.core.management.base import BaseCommand

from vtpass.services import VTpass


class Command(BaseCommand):
    help = "Sync VTpass categories, services and plans into the local catalogue."

    def add_arguments(self, parser):
        parser.add_argument("--category", action="append", dest="categories",
                            help="Only sync this category identifier (repeatable).")
        parser.add_argument("--service", action="append", dest="services",
                            help="Only refresh plans for this service ID (repeatable).")
        parser.add_argument("--no-variations", action="store_true", help="Skip plans/bouquets.")

    def handle(self, *args, **options):
        vt = VTpass()
        if options["services"]:
            for service_id in options["services"]:
                count = vt.catalog.sync_variations(service_id)
                self.stdout.write(f"{service_id}: {count} plan(s)")
            return
        stats = vt.catalog.sync(categories=options["categories"], with_variations=not options["no_variations"])
        self.stdout.write(self.style.SUCCESS(
            f"Synced {stats['categories']} categories, {stats['services']} services, {stats['variations']} plans."
        ))
