"""
Persisted scoreboard + fair role rotation.

Each player's record: {"points": int, "civilian": int, "undercover": int, "mrwhite": int}
The role counts are used to weight future role draws so the same one or
two people don't keep landing Undercover/Mr. White every round.
"""
import json
import os
import random

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "scores.json")


def _ensure_file():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump({}, f)


def _blank():
    return {"points": 0, "civilian": 0, "undercover": 0, "mrwhite": 0}


def load_scores():
    _ensure_file()
    with open(DATA_FILE, "r") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError:
            raw = {}
    fixed = {}
    for name, val in raw.items():
        rec = _blank()
        if isinstance(val, dict):
            rec.update(val)
        else:
            rec["points"] = val
        fixed[name] = rec
    return fixed


def save_scores(scores):
    _ensure_file()
    with open(DATA_FILE, "w") as f:
        json.dump(scores, f, indent=2)


def known_names():
    return sorted(load_scores().keys())


def _weighted_sample(indices, weights, k):
    """Weighted random sample without replacement (Efraimidis-Spirakis)."""
    if k <= 0:
        return []
    keyed = []
    for i, w in zip(indices, weights):
        w = max(w, 0.0001)
        key = random.random() ** (1.0 / w)
        keyed.append((key, i))
    keyed.sort(reverse=True)
    return [i for _, i in keyed[:k]]


def assign_roles(player_names, num_undercover, num_mrwhite):
    """
    Returns a list of roles parallel to player_names, e.g.
    ['civilian', 'undercover', 'civilian', 'mrwhite', ...]

    Picks Undercover/Mr. White with weight inversely proportional to how
    often that player has already played that role, so roles rotate
    around the group instead of always landing on the same people.
    """
    scores = load_scores()
    n = len(player_names)
    roles = ["civilian"] * n
    indices = list(range(n))

    def weight_for(idx, role):
        rec = scores.get(player_names[idx], _blank())
        return 1.0 / (rec[role] + 1)

    uc_weights = [weight_for(i, "undercover") for i in indices]
    undercover_idx = _weighted_sample(indices, uc_weights, num_undercover)

    remaining = [i for i in indices if i not in undercover_idx]
    mw_weights = [weight_for(i, "mrwhite") for i in remaining]
    mrwhite_idx = _weighted_sample(remaining, mw_weights, num_mrwhite)

    for i in undercover_idx:
        roles[i] = "undercover"
    for i in mrwhite_idx:
        roles[i] = "mrwhite"

    return roles


def build_turn_order(players):
    """
    Returns a shuffled list of player ids (speaking order for the round).
    Mr. White never goes first - they don't know the word yet and would
    have nothing to say, so the first slot is reserved for anyone else.
    """
    order = [p["id"] for p in players]
    random.shuffle(order)

    by_id = {p["id"]: p for p in players}
    if by_id[order[0]]["role"] == "mrwhite":
        for i in range(1, len(order)):
            if by_id[order[i]]["role"] != "mrwhite":
                order[0], order[i] = order[i], order[0]
                break
    return order


def record_round(players, winner):
    """
    Call once per finished game. Bumps each player's role-played count
    (for fair future rotation) and awards points to the winning side.
    Returns {name: points_gained} for this round.
    """
    scores = load_scores()
    gained = {}

    for p in players:
        rec = scores.setdefault(p["name"], _blank())
        rec[p["role"]] = rec.get(p["role"], 0) + 1

        points = 0
        if winner == "civilians" and p["role"] == "civilian":
            points = 1
        elif winner == "undercover" and p["role"] in ("undercover", "mrwhite") and p["alive"]:
            points = 2
        elif winner == "mrwhite" and p["role"] == "mrwhite":
            points = 3

        if points:
            rec["points"] += points
            gained[p["name"]] = points

    save_scores(scores)
    return gained
