"""A single in-process worker for personal use; no persistent history."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
import logging
from threading import Lock
from uuid import uuid4

import chess.svg
from werkzeug.utils import secure_filename

from chess_analysis import stream_game_analysis

logger = logging.getLogger(__name__)


@dataclass
class AnalysisJob:
    id: str
    game_name: str
    title: str
    player: int
    total: int
    settings: dict
    initial_svg: str
    result: str
    state: str = "queued"
    moves: list = field(default_factory=list)
    final_svg: str | None = None
    final_checkmate: bool = False
    error: str | None = None
    lock: Lock = field(default_factory=Lock, repr=False)

    def snapshot(self, since=0):
        with self.lock:
            return {
                "id": self.id, "title": self.title, "player": self.player,
                "total": self.total, "available": len(self.moves), "state": self.state,
                "moves": self.moves[since:], "settings": self.settings, "error": self.error,
                "initial_svg": self.initial_svg, "final_svg": self.final_svg,
                "final_checkmate": self.final_checkmate,
                "result": self.result, "game_name": self.game_name,
            }


class JobManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stockfish-analysis")
        self.jobs = {}
        self.lock = Lock()

    def start(self, game, player, title, settings):
        job_id = uuid4().hex
        name = secure_filename(title)[:80] or "partida"
        job = AnalysisJob(
            id=job_id, game_name=f"{name}_{job_id}", title=title or "Partida sense nom",
            player=player, total=sum(1 for _ in game.mainline_moves()), settings=asdict(settings),
            initial_svg=chess.svg.board(game.board(), flipped=(player == 1)),
            result=game.headers.get("Result", "*"),
        )
        with self.lock:
            self.jobs[job_id] = job
        self.executor.submit(self._run, job, game, settings)
        return job

    def get(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def _run(self, job, game, settings):
        try:
            with job.lock:
                job.state = "running"
            for move in stream_game_analysis(game, job.player, job.game_name, settings):
                with job.lock:
                    job.moves.append(move)
            final_board = game.end().board()
            final_svg = chess.svg.board(final_board, flipped=(job.player == 1))
            with job.lock:
                job.final_svg = final_svg
                job.final_checkmate = final_board.is_checkmate()
                if job.result == "*" and final_board.is_game_over():
                    job.result = final_board.result()
                job.state = "complete"
        except Exception:
            logger.exception("Analysis failed for job %s", job.id)
            with job.lock:
                job.error = "No s'ha pogut completar l'anàlisi. Revisa que Stockfish funcioni i torna-ho a provar."
                job.state = "error"
