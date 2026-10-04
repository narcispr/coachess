"""Stockfish searches and incremental analysis, independent of Flask."""
import io
import math
from pathlib import Path

import chess.engine
import chess.pgn
import chess.svg

from analysis_settings import AnalysisSettings
from stockfish_config import ROOT, stockfish_path

STATIC_DIR = ROOT / "static"
COLORS = {
    "best": "#4d91e3", "excellent": "#4ba879", "good": "#8bbf83",
    "inaccuracy": "#e1b638", "mistake": "#e48c3c", "blunder": "#df6464",
}


def import_pgn(pgn: str) -> chess.pgn.Game:
    if not isinstance(pgn, str) or not pgn.strip():
        raise ValueError("Introdueix una partida en format PGN.")
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None or game.errors or not game.board().is_valid():
        raise ValueError("El PGN conté una partida o una posició invàlida.")
    if not any(game.mainline_moves()):
        raise ValueError("El PGN no conté cap jugada.")
    if game.board().uci_variant != "chess":
        raise ValueError("Aquesta aplicació analitza partides d'escacs estàndard.")
    return game


def get_score(info: chess.engine.InfoDict, color: chess.Color) -> tuple[int, int | None]:
    score = info["score"].pov(color)
    return score.score(mate_score=10000), score.mate()


def win_percent(score: int) -> float:
    # Lichess's empirical conversion. This is not Stockfish's self-play WDL.
    score = max(-10000, min(10000, score))
    return 100 / (1 + math.exp(-0.00368208 * score))


def analyse_movement(board, move, color, engine=None, settings=None):
    """Compare top root candidates with a separate forced-root search."""
    settings = settings or AnalysisSettings()
    if engine is None:
        with chess.engine.SimpleEngine.popen_uci(stockfish_path()) as owned:
            return analyse_movement(board, move, color, owned, settings)
    if move not in board.legal_moves:
        raise ValueError("La jugada no és legal en aquesta posició.")
    limit = chess.engine.Limit(time=settings.time_limit)
    candidates = engine.analyse(board, limit, multipv=min(settings.multipv, board.legal_moves.count()))
    scores = []
    for candidate in candidates:
        if candidate.get("pv"):
            score, mate = get_score(candidate, color)
            scores.append((candidate["pv"][0], score, mate))
    # Always search the actual move, including when it appeared among the candidates.
    actual = engine.analyse(board, limit, root_moves=[move])
    score, mate = get_score(actual, color)
    real_score = (move, score, mate)
    scores = [candidate for candidate in scores if candidate[0] != move]
    scores.append(real_score)
    return real_score, scores


def _winning_mate(score):
    return score[2] is not None and score[1] > 0


def movement_assessment(real_score, scores, settings=None):
    settings = settings or AnalysisSettings()
    best = max(scores, key=lambda item: (item[1], -item[2] if item[2] is not None else 0))
    loss_cp = max(0, best[1] - real_score[1])
    loss = max(0, win_percent(best[1]) - win_percent(real_score[1]))
    if best[0] == real_score[0]:
        category, text = "best", "Millor jugada"
    elif loss >= settings.blunder:
        category, text = "blunder", "Error greu"
    elif loss >= settings.mistake:
        category, text = "mistake", "Error"
    elif loss >= settings.inaccuracy:
        category, text = "inaccuracy", "Imprecisió"
    elif loss <= settings.excellent:
        category, text = "excellent", "Jugada excel·lent"
    else:
        category, text = "good", "Bona jugada"

    # Limited MultiPV cannot prove how many legal moves avoid mate. Do not infer it.
    if _winning_mate(best) and not _winning_mate(real_score):
        text += f" · Mat no aprofitat en {best[2]}"
    elif _winning_mate(best) and _winning_mate(real_score):
        if real_score[2] > best[2] + settings.mate_slack:
            text += f" · Manté el mat, però en {real_score[2]} jugades en lloc de {best[2]}"
    if real_score[2] is not None and real_score[1] < 0:
        if best[2] is None or best[1] >= 0:
            text += f" · Permet un mat en {abs(real_score[2])}"
        else:
            text += f" · Mat en contra en {abs(real_score[2])}"

    alternatives = sorted(
        (item for item in scores if item[0] != real_score[0]
         and best[1] - item[1] <= settings.alternative_tolerance),
        key=lambda item: item[1], reverse=True,
    )
    return {
        "category": category, "text": text, "loss_cp": loss_cp,
        "loss_percent": round(loss, 2), "best_uci": best[0].uci(),
    }, alternatives


def check_movement(real_score, scores, settings=None):
    """Compatibility wrapper for callers using the original tuple interface."""
    assessment, alternatives = movement_assessment(real_score, scores, settings)
    return COLORS[assessment["category"]], alternatives, (-assessment["loss_cp"], assessment["text"])


def display_board(board, arrows, player, filename, create_imgs):
    svg = chess.svg.board(board, arrows=arrows, size=450, flipped=(player == 1))
    if filename is not None and create_imgs:
        Path(filename).write_text(svg, encoding="utf-8")
    return svg


def _output_dir(game_name):
    if not game_name or game_name in (".", "..") or Path(game_name).name != game_name or "\\" in game_name:
        raise ValueError("El nom de la partida no pot contenir una ruta.")
    return STATIC_DIR / game_name


def _iter_game(game, board, player, output_dir, create_imgs, engine, settings):
    color = chess.WHITE if player == 0 else chess.BLACK
    for index, move in enumerate(game.mainline_moves()):
        san = board.san(move)
        move_number = board.fullmove_number
        mover = "white" if board.turn else "black"
        assessment = None
        alternatives = []
        arrows = [chess.svg.Arrow(move.from_square, move.to_square, color="#89919b")]
        if board.turn == color:
            real, candidates = analyse_movement(board, move, color, engine, settings)
            score, mate = real[1:]
            assessment, alternatives = movement_assessment(real, candidates, settings)
            arrows = [chess.svg.Arrow(move.from_square, move.to_square,
                                      color=COLORS[assessment["category"]])]
        else:
            board.push(move)
            try:
                score, mate = get_score(engine.analyse(board, chess.engine.Limit(time=settings.time_limit)), color)
            finally:
                board.pop()
        filename = f"move_{index:03d}.svg"
        solution_filename = f"move_{index:03d}_sol.svg" if assessment else None
        display_board(board, arrows, player, output_dir / filename, create_imgs)
        candidate_details = []
        if assessment:
            for rank, alternative in enumerate(alternatives):
                candidate_move, candidate_score, candidate_mate = alternative
                candidate_details.append({
                    "san": board.san(candidate_move), "score": candidate_score, "mate": candidate_mate,
                })
                arrows.append(chess.svg.Arrow(candidate_move.from_square, candidate_move.to_square,
                                              color="#bc66d2" if rank == 0 else "#dda1ce"))
            display_board(board, arrows, player, output_dir / solution_filename, create_imgs)
        board.push(move)
        # Publish only after every image for this move is fully written.
        yield {
            "index": index, "san": san, "uci": move.uci(), "mover": mover,
            "move_number": move_number, "score": score, "mate": mate,
            "assessment": assessment, "alternatives": candidate_details,
            "image": filename, "solution_image": solution_filename,
        }


def stream_game_analysis(game, player, game_name, settings=None, create_imgs=True, board=None):
    if player not in (0, 1):
        raise ValueError("El jugador ha de ser 0 (blanques) o 1 (negres).")
    settings = settings or AnalysisSettings()
    output_dir = _output_dir(game_name)
    if create_imgs:
        output_dir.mkdir(parents=True, exist_ok=True)
    board = board if board is not None else game.board()
    with chess.engine.SimpleEngine.popen_uci(stockfish_path()) as engine:
        engine.configure({"Threads": 1, "Hash": 32})
        yield from _iter_game(game, board, player, output_dir, create_imgs, engine, settings)


def analyse_game(game, board, player, game_name, create_imgs=True, settings=None):
    """Collect the streaming results for scripts using the original API."""
    results = list(stream_game_analysis(game, player, game_name, settings, create_imgs, board))
    return (
        [item["score"] for item in results],
        [(-item["assessment"]["loss_cp"], item["assessment"]["text"]) if item["assessment"] else None
         for item in results],
        [item["uci"] for item in results],
    )
