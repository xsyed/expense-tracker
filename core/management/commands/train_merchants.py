from __future__ import annotations

import datetime
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from core.merchant_utils import normalize_merchant
from core.models import MerchantRule, Transaction, User


class Command(BaseCommand):
    help = "Build merchant→category rules from existing categorized transactions."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--user", type=int, help="Train rules for a specific user ID only.")

    def handle(self, *args: Any, **options: Any) -> None:
        users = User.objects.all()
        if options["user"]:
            users = users.filter(pk=options["user"])

        for user in users:
            txs = (
                Transaction.objects.filter(expense_month__user=user, category__isnull=False)
                .values_list("description", "category_id", "updated_at")
                .iterator()
            )

            merchant_counts: dict[str, Counter[int]] = {}
            merchant_latest: dict[tuple[str, int], datetime.datetime] = {}

            for description, category_id, updated_at in txs:
                normalized = normalize_merchant(description)
                if normalized not in merchant_counts:
                    merchant_counts[normalized] = Counter()
                merchant_counts[normalized][category_id] += 1
                key = (normalized, category_id)
                if key not in merchant_latest or updated_at > merchant_latest[key]:
                    merchant_latest[key] = updated_at

            rule_count = 0
            for normalized, counts in merchant_counts.items():
                max_count = counts.most_common(1)[0][1]
                tied = [cid for cid, cnt in counts.items() if cnt == max_count]
                if len(tied) == 1:
                    best_category_id = tied[0]
                else:
                    best_category_id = max(tied, key=lambda cid: merchant_latest[(normalized, cid)])

                MerchantRule.objects.update_or_create(
                    user=user,
                    normalized_name=normalized,
                    defaults={"category_id": best_category_id},
                )
                rule_count += 1

            self.stdout.write(f"Created/updated {rule_count} rules for {user.email}")
