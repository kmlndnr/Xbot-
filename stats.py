from db import get_stats, get_all_drafts

SEPARATOR = "─" * 60


def print_stats():
    s = get_stats()

    print(f"\n{SEPARATOR}")
    print("  STATISTIKEN")
    print(SEPARATOR)

    approval_rate = (s["approved"] / s["total"] * 100) if s["total"] > 0 else 0

    print(f"\n  Mentions verarbeitet:")
    print(f"    Gesamt:      {s['total']}")
    print(f"    Approved:    {s['approved']}")
    print(f"    Rejected:    {s['rejected']}")
    print(f"    Pending:     {s['pending']}")
    print(f"    Approval-Rate: {approval_rate:.1f}%")

    if s["total_dms"] > 0:
        print(f"\n  Direktnachrichten:")
        print(f"    Gesamt:      {s['total_dms']}")
        print(f"    Geantwortet: {s['approved_dms']}")

    if s["top_mentioners"]:
        print(f"\n  Top Erwähner:")
        for i, row in enumerate(s["top_mentioners"], 1):
            print(f"    {i}. @{row['author_username']} – {row['cnt']}x")

    if s["daily_activity"]:
        print(f"\n  Aktivität letzte 7 Tage:")
        max_cnt = max(r["cnt"] for r in s["daily_activity"]) or 1
        for row in s["daily_activity"]:
            bar_len = int(row["cnt"] / max_cnt * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {row['day']}  {bar}  {row['cnt']}")

    print(f"\n{SEPARATOR}")
