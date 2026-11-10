"""Fixed choices for why a setup was passed on and what went wrong in a trade.

Keys are stored; labels are only for display, so a label can be reworded
without touching saved entries.
"""

OTHER_REASON = "other"
FOLLOWED_PLAN = "followed_plan"

PASS_REASON_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("The app's read", [
        ("low_sykes", "Low Sykes grade"),
        ("low_score", "Low score"),
        ("no_verdict", "No verdict / no clear edge"),
        ("leans_short", "Leans short"),
        ("bearish_pattern", "Bearish pattern too"),
        ("low_reward_risk", "Reward:risk too low (target capped)"),
        ("risk_too_big", "Risk % too big (stop too far)"),
        ("stop_too_tight", "Stop too tight"),
    ]),
    ("Timing", [
        ("missed_it", "Missed it"),
        ("too_early", "Too early (not confirmed)"),
        ("too_late", "Too late / extended"),
        ("chasing", "Would be chasing"),
        ("bad_time_of_day", "Bad time of day"),
        ("extended_hours", "Extended hours (thin, wide spread)"),
    ]),
    ("The stock", [
        ("float_too_big", "Float too big"),
        ("low_relative_volume", "Low relative volume"),
        ("thin_volume", "Thin volume / wide spread"),
        ("price_outside_range", "Price outside my range"),
        ("ran_too_far", "Already ran too far today"),
        ("resistance_overhead", "Resistance overhead"),
        ("choppy", "Choppy, no clean level"),
        ("halt_risk", "Halt risk"),
    ]),
    ("News", [
        ("no_catalyst", "No catalyst"),
        ("weak_news", "Weak or old news"),
        ("dilution_risk", "Dilution risk (offering, warrants, shelf)"),
        ("reverse_split", "Recent reverse split"),
        ("company_red_flags", "Company red flags"),
    ]),
    ("Market", [
        ("weak_market", "Weak market / small caps cold"),
        ("sector_not_moving", "Sector not moving"),
    ]),
    ("Me", [
        ("max_daily_loss", "Hit max daily loss"),
        ("daily_goal", "Hit daily goal, done for the day"),
        ("already_in_position", "Already in a position"),
        ("pdt_or_buying_power", "Pattern day trader limit / buying power"),
        ("not_focused", "Not focused / tilted"),
        ("not_in_playbook", "Not in my playbook"),
        (OTHER_REASON, "Other"),
    ]),
]

MISTAKES: list[tuple[str, str]] = [
    ("chased", "Chased"),
    ("oversized", "Oversized"),
    ("moved_stop", "Moved my stop"),
    ("held_loser", "Held a loser"),
    ("sold_too_early", "Sold too early"),
    ("revenge_trade", "Revenge trade"),
    ("fomo", "FOMO"),
    (FOLLOWED_PLAN, "Followed the plan"),
]

PASS_REASON_KEYS = frozenset(key for _, items in PASS_REASON_GROUPS for key, _ in items)
MISTAKE_KEYS = frozenset(key for key, _ in MISTAKES)
