from flask import Flask, render_template, request, redirect, url_for, session

from word_bank import get_categories, pick_word_pair
import store
import friday

app = Flask(__name__)
app.secret_key = "undercover-dev-secret-change-me"

TOTAL_ROUNDS = 10


# ---------------------------------------------------------------- helpers --

def reset_game():
    session.clear()


def get_players():
    return session.get("players", [])


def save_players(players):
    session["players"] = players


def alive_players():
    return [p for p in get_players() if p["alive"]]


def check_winner():
    """Return 'civilians', 'undercover', or None if the game continues."""
    alive = alive_players()
    civ = [p for p in alive if p["role"] == "civilian"]
    threat = [p for p in alive if p["role"] in ("undercover", "mrwhite")]

    if not threat:
        return "civilians"
    if len(threat) >= len(civ):
        return "undercover"
    return None


def build_round(player_names, num_undercover, num_mrwhite, category):
    """Shared by /start and /rematch: assigns roles+word, sets up session state."""
    civ_word, undercover_word = pick_word_pair(category)
    roles = store.assign_roles(player_names, num_undercover, num_mrwhite)

    players = []
    for idx, (name, role) in enumerate(zip(player_names, roles)):
        if role == "civilian":
            word = civ_word
        elif role == "undercover":
            word = undercover_word
        else:
            word = ""
        players.append({
            "id": idx,
            "name": name,
            "role": role,
            "word": word,
            "alive": True,
        })

    turn_order = store.build_turn_order(players)

    session["player_names"] = player_names
    session["players"] = players
    session["civ_word"] = civ_word
    session["category"] = category
    session["reveal_index"] = 0
    session["winner"] = None
    session["scored"] = False
    session["gained"] = {}
    session["turn_order"] = turn_order
    session["round_first_out"] = None
    session["round_correct_guess"] = None
    session["round_wrong_guess"] = None


# ------------------------------------------------------------------ views --

@app.route("/")
def home():
    reset_game()
    return render_template("setup.html", categories=get_categories())


@app.route("/names", methods=["POST"])
def names():
    try:
        num_players = int(request.form.get("num_players", 0))
        num_undercover = int(request.form.get("num_undercover", 0))
        num_mrwhite = int(request.form.get("num_mrwhite", 0))
    except ValueError:
        return redirect(url_for("home"))

    category = request.form.get("category", "mix")
    errors = []

    if num_players < 3 or num_players > 20:
        errors.append("Players must be between 3 and 20.")
    if num_undercover < 0 or num_mrwhite < 0:
        errors.append("Role counts can't be negative.")
    if num_undercover + num_mrwhite >= num_players:
        errors.append("You need more civilians than undercover + Mr. White combined.")

    if errors:
        return render_template(
            "setup.html", categories=get_categories(), errors=errors,
            num_players=num_players, num_undercover=num_undercover,
            num_mrwhite=num_mrwhite, category=category,
        )

    session["num_players"] = num_players
    session["num_undercover"] = num_undercover
    session["num_mrwhite"] = num_mrwhite
    session["category"] = category

    return render_template(
        "names.html", num_players=num_players, known_names=store.known_names()
    )


@app.route("/start", methods=["POST"])
def start():
    num_players = session.get("num_players")
    num_undercover = session.get("num_undercover")
    num_mrwhite = session.get("num_mrwhite")
    category = session.get("category", "mix")

    if not num_players:
        return redirect(url_for("home"))

    player_names = []
    for i in range(1, num_players + 1):
        name = request.form.get(f"name_{i}", "").strip()
        player_names.append(name or f"Player {i}")

    session["match_round"] = 1
    session["match_totals"] = {}
    session["match_history"] = []
    build_round(player_names, num_undercover, num_mrwhite, category)
    return redirect(url_for("reveal"))


@app.route("/rematch", methods=["POST"])
def rematch():
    """Same roster, freshly (and fairly) re-rolled roles + word — no retyping names.
    Advances to the next round of the current 10-round match."""
    player_names = session.get("player_names")
    num_undercover = session.get("num_undercover")
    num_mrwhite = session.get("num_mrwhite")
    category = session.get("category", "mix")

    if not player_names:
        return redirect(url_for("home"))

    current_round = session.get("match_round", 1)
    if current_round >= TOTAL_ROUNDS:
        # Previous match just finished — start a fresh 10-round match.
        session["match_round"] = 1
        session["match_totals"] = {}
        session["match_history"] = []
    else:
        session["match_round"] = current_round + 1

    build_round(player_names, num_undercover, num_mrwhite, category)
    return redirect(url_for("reveal"))


@app.route("/reveal")
def reveal():
    players = get_players()
    idx = session.get("reveal_index", 0)
    if not players:
        return redirect(url_for("home"))
    if idx >= len(players):
        return redirect(url_for("board"))
    player = players[idx]
    hint = friday.mrwhite_hint(session.get("category", "mix")) if player["role"] == "mrwhite" else None
    return render_template(
        "reveal.html",
        player=player,
        idx=idx + 1,
        total=len(players),
        round_num=session.get("match_round", 1),
        total_rounds=TOTAL_ROUNDS,
        mrwhite_hint=hint,
    )


@app.route("/reveal/next", methods=["POST"])
def reveal_next():
    session["reveal_index"] = session.get("reveal_index", 0) + 1
    return redirect(url_for("reveal"))


@app.route("/board")
def board():
    winner = session.get("winner")
    if winner:
        return redirect(url_for("result"))
    players = get_players()
    by_id = {p["id"]: p for p in players}
    turn_order = session.get("turn_order") or [p["id"] for p in players]
    order_names = [by_id[i]["name"] for i in turn_order if i in by_id]
    starter = order_names[0] if order_names else None
    return render_template(
        "board.html",
        players=players,
        starter=starter,
        turn_order=order_names,
        round_num=session.get("match_round", 1),
        total_rounds=TOTAL_ROUNDS,
    )


@app.route("/eliminate/<int:pid>", methods=["POST"])
def eliminate(pid):
    players = get_players()
    for p in players:
        if p["id"] == pid:
            p["alive"] = False
            save_players(players)
            if session.get("round_first_out") is None:
                session["round_first_out"] = p["name"]
            if p["role"] == "mrwhite":
                return redirect(url_for("guess", pid=pid))
            break

    winner = check_winner()
    if winner:
        session["winner"] = winner
        return redirect(url_for("result"))
    return redirect(url_for("board"))


@app.route("/guess/<int:pid>", methods=["GET", "POST"])
def guess(pid):
    players = get_players()
    player = next((p for p in players if p["id"] == pid), None)
    if not player:
        return redirect(url_for("board"))

    if request.method == "POST":
        guess_text = request.form.get("guess", "").strip().lower()
        civ_word = session.get("civ_word", "").strip().lower()
        if guess_text == civ_word:
            session["winner"] = "mrwhite"
            session["round_correct_guess"] = player["name"]
            return redirect(url_for("result"))

        session["round_wrong_guess"] = player["name"]
        winner = check_winner()
        if winner:
            session["winner"] = winner
        return redirect(url_for("board"))

    return render_template("guess.html", player=player)


@app.route("/result")
def result():
    winner = session.get("winner")
    if not winner:
        return redirect(url_for("board"))

    if not session.get("scored"):
        gained = store.record_round(get_players(), winner)
        session["scored"] = True
        session["gained"] = gained

        totals = session.get("match_totals", {})
        for name, pts in gained.items():
            totals[name] = totals.get(name, 0) + pts
        session["match_totals"] = totals

        history = session.get("match_history", [])
        history.append({
            "winner": winner,
            "players": [
                {"name": p["name"], "role": p["role"], "alive": p["alive"]}
                for p in get_players()
            ],
            "first_out": session.get("round_first_out"),
            "correct_guess": session.get("round_correct_guess"),
            "wrong_guess": session.get("round_wrong_guess"),
        })
        session["match_history"] = history

    round_num = session.get("match_round", 1)
    is_final_round = round_num >= TOTAL_ROUNDS
    totals = session.get("match_totals", {})
    ranked_totals = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)

    debrief = None
    round_comment = None
    if is_final_round:
        debrief = friday.build_debrief(session.get("match_history", []), totals)
    else:
        history = session.get("match_history", [])
        if history:
            round_comment = friday.build_round_comment(history[-1], totals)

    return render_template(
        "result.html",
        winner=winner,
        players=get_players(),
        civ_word=session.get("civ_word", ""),
        gained=session.get("gained", {}),
        round_num=round_num,
        total_rounds=TOTAL_ROUNDS,
        is_final_round=is_final_round,
        ranked_totals=ranked_totals,
        debrief=debrief,
        round_comment=round_comment,
    )


@app.route("/leaderboard")
def leaderboard():
    scores = store.load_scores()
    ranked = sorted(scores.items(), key=lambda kv: kv[1]["points"], reverse=True)
    return render_template("leaderboard.html", ranked=ranked)


@app.route("/restart")
def restart():
    reset_game()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
