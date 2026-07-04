from __future__ import annotations

import datetime
import time
from typing import cast

from django.core.management.base import BaseCommand, CommandParser

from core.advisor_worker import mark_stale_running_runs, process_next_advisor_run


class Command(BaseCommand):
    help = "Process pending advisor runs from the database queue."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true", help="Process at most one pending run and exit.")
        parser.add_argument("--max-runs", type=int, default=0, help="Process at most this many runs; 0 means forever.")
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=2.0,
            help="Seconds to wait when no runs are pending.",
        )
        parser.add_argument(
            "--stale-after",
            type=int,
            default=900,
            help="Seconds before a running run is considered stale and failed.",
        )

    def handle(self, *args: object, **options: object) -> None:
        once = cast(bool, options["once"])
        max_runs = cast(int, options["max_runs"])
        poll_interval = cast(float, options["poll_interval"])
        stale_after = datetime.timedelta(seconds=cast(int, options["stale_after"]))
        processed = 0

        while True:
            failed_count = mark_stale_running_runs(stale_after=stale_after)
            if failed_count:
                self.stdout.write(f"Marked {failed_count} stale advisor run(s) as failed.")

            did_process = process_next_advisor_run()
            if did_process:
                processed += 1
                self.stdout.write("Processed one advisor run.")
            if once or (max_runs and processed >= max_runs):
                return
            if not did_process:
                time.sleep(poll_interval)
