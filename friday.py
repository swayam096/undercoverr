"""
Friday — the case analyst who delivers round commentary, the end-of-match
debrief, and a pre-round coaching tip for Mr. White.

Pure presentation logic: turns raw match history into short spoken-style
lines plus a handful of superlative badges. No state, no side effects,
nothing persisted — she only ever talks about the match that just
finished (or the round that just finished).
"""
import random
from collections import Counter

_CATEGORY_TALK = {
    "movies": "something people watch",
    "actors": "someone people would recognize",
    "things": "something you'd find lying around the house",
    "subjects": "something you'd study or argue about",
    "space": "something way bigger than this room",
    "sports": "something people compete at",
    "animals": "something alive and not human",
    "places": "somewhere you could actually go",
    "mix": "today's category",
}

_MRWHITE_OPENERS = [
    'Keep it vague — call it "{topic}" and let the table fill in the blanks.',
    "Don't commit to specifics. Just confirm it's {topic} and watch how the others react.",
    "Borrow the shape of someone else's clue and loosen it. Buy yourself a round before anyone's sure.",
    'Ask a question instead of giving an answer — "isn\'t that kind of {topic}?" works fine.',
    'Lead with a mood, not a fact — "it\'s got a certain vibe" buys time without lying.',
    "Agree with the last clue and add nothing. Silence reads better than a wrong detail.",
]


def build_debrief(match_history, match_totals):
    """
    match_history: list of round records, each shaped like
        {
            "winner": "civilians" | "undercover" | "mrwhite",
            "players": [{"name": str, "role": str, "alive": bool}, ...],
            "first_out": str | None,     # name of the first player voted out
            "correct_guess": str | None, # name of a Mr. White who guessed right
        }
    match_totals: {name: points_this_match}

    Returns {"intro": str, "badges": [{"name", "title", "quip"}, ...]}
    """
    if not match_history or not match_totals:
        return {"intro": "No data on file yet.", "badges": []}

    survived_undercover = Counter()
    civilian_wins = Counter()
    correct_guesses = Counter()
    wrong_guesses = Counter()
    first_out = Counter()

    for rnd in match_history:
        winner = rnd.get("winner")
        for p in rnd.get("players", []):
            if p["role"] in ("undercover", "mrwhite") and p["alive"]:
                survived_undercover[p["name"]] += 1
            if p["role"] == "civilian" and winner == "civilians":
                civilian_wins[p["name"]] += 1
        if rnd.get("first_out"):
            first_out[rnd["first_out"]] += 1
        if rnd.get("correct_guess"):
            correct_guesses[rnd["correct_guess"]] += 1
        if rnd.get("wrong_guess"):
            wrong_guesses[rnd["wrong_guess"]] += 1

    def top(counter):
        if not counter:
            return None
        name, value = counter.most_common(1)[0]
        return (name, value) if value >= 1 else None

    badges = []

    top_scorer = max(match_totals.items(), key=lambda kv: kv[1], default=None)
    if top_scorer and top_scorer[1] > 0:
        badges.append({
            "name": top_scorer[0],
            "title": "Top Operative",
            "quip": "Closed more cases than anyone else at this table.",
        })

    t = top(survived_undercover)
    if t:
        badges.append({
            "name": t[0],
            "title": "Master of Disguise",
            "quip": f"Played the threat and walked away clean {t[1]}x.",
        })

    t = top(correct_guesses)
    if t:
        badges.append({
            "name": t[0],
            "title": "Silent Assassin",
            "quip": "Guessed the civilians' word cold, with nothing to go on.",
        })

    t = top(civilian_wins)
    if t:
        badges.append({
            "name": t[0],
            "title": "Sharpest Detective",
            "quip": "Read the table right, round after round.",
        })

    t = top(first_out)
    if t and t[1] >= 2:
        badges.append({
            "name": t[0],
            "title": "Easy Target",
            "quip": f"First one named {t[1]}x. Might want a better poker face.",
        })

    # Opposite of Silent Assassin: guessed every time they got the chance,
    # and never once landed it.
    wrong_only = {
        name: count for name, count in wrong_guesses.items()
        if count >= 2 and correct_guesses.get(name, 0) == 0
    }
    if wrong_only:
        name, count = max(wrong_only.items(), key=lambda kv: kv[1])
        badges.append({
            "name": name,
            "title": "Cold Trail",
            "quip": f"Guessed {count}x, never once got warm.",
        })

    totals_sorted = sorted(match_totals.items(), key=lambda kv: kv[1], reverse=True)
    if len(totals_sorted) >= 2 and totals_sorted[0][1] > 0:
        gap = totals_sorted[0][1] - totals_sorted[1][1]
        if gap <= 1:
            intro = "Tight one. That came down to a coin flip."
        elif gap >= 6:
            intro = f"No contest. {totals_sorted[0][0]} ran the table."
        else:
            intro = f"Solid case work all around — {totals_sorted[0][0]} edges it."
    else:
        intro = "Case closed. Nobody separated themselves this match."

    return {"intro": intro, "badges": badges}


def build_round_comment(round_record, totals):
    """
    One-line Friday commentary shown right after a single round (not the
    final match). round_record is shaped like one entry of match_history
    (see build_debrief docstring). totals is the running match_totals
    after this round has been scored.
    """
    if not round_record:
        return "Round logged. On to the next one."

    winner = round_record.get("winner")
    first_out = round_record.get("first_out")
    correct_guess = round_record.get("correct_guess")
    wrong_guess = round_record.get("wrong_guess")

    if winner == "mrwhite" and correct_guess:
        line = f"Bold call from {correct_guess} — walked in blind and named it anyway."
    elif wrong_guess:
        line = f"{wrong_guess} took the guess and missed. Costly."
    elif winner == "civilians" and first_out:
        line = f"Civilians hold the room. {first_out} didn't last long, but the rest closed it out."
    elif winner == "civilians":
        line = "Clean sweep for the civilians this round."
    elif winner == "undercover":
        line = "The undercover crew talked their way through. Nobody clocked them in time."
    else:
        line = "Round logged. On to the next one."

    if totals:
        top_name, top_score = max(totals.items(), key=lambda kv: kv[1])
        if top_score > 0:
            line += f" {top_name} leads the case file at {top_score}."

    return line


def mrwhite_hint(category):
    """A short pre-round coaching line for a Mr. White player - something
    to say when their turn comes up, without revealing an actual word."""
    topic = _CATEGORY_TALK.get(category, "today's category")
    return random.choice(_MRWHITE_OPENERS).format(topic=topic)
