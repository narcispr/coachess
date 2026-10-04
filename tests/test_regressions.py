from dataclasses import asdict
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

import chess
import chess.engine

import chess_analysis as analysis
from analysis_jobs import JobManager
from analysis_settings import AnalysisSettings
from coachess import app
from scripts.install_stockfish import safe_target
from stockfish_config import stockfish_path


class FakeEngine:
    def analyse(self, board, limit, multipv=None, root_moves=None):
        info = {"score": chess.engine.PovScore(chess.engine.Cp(120), chess.WHITE)}
        if multipv is not None:
            return [dict(info, pv=[move]) for move in list(board.legal_moves)[:multipv]]
        return dict(info, pv=root_moves or [])


class AnalysisTests(unittest.TestCase):
    def test_invalid_pgn_is_rejected(self):
        for pgn in (None, '', 'not a game', '[Event "Empty"]\n\n*', '1. e4 e5 2. Bh6 *'):
            with self.subTest(pgn=pgn), self.assertRaises(ValueError):
                analysis.import_pgn(pgn)

    def test_scores_keep_player_perspective(self):
        game = analysis.import_pgn('1. e4 e5 2. Nf3 *')
        for player, expected in ((0, [120] * 3), (1, [-120] * 3)):
            with patch.object(analysis, 'display_board'):
                moves = list(analysis._iter_game(game, game.board(), player, Path('/unused'), False, FakeEngine(), AnalysisSettings()))
            self.assertEqual([move['score'] for move in moves], expected)
            self.assertEqual([move['assessment'] is not None for move in moves], [i % 2 == player for i in range(3)])
            self.assertEqual([move['san'] for move in moves], ['e4', 'e5', 'Nf3'])

    def test_black_to_move_fen_uses_actual_turn(self):
        game = analysis.import_pgn('[SetUp "1"]\n[FEN "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 7"]\n\n7... e5 8. e4 *')
        with patch.object(analysis, 'display_board'):
            moves = list(analysis._iter_game(game, game.board(), 1, Path('/unused'), False, FakeEngine(), AnalysisSettings()))
        self.assertIsNotNone(moves[0]['assessment'])
        self.assertIsNone(moves[1]['assessment'])
        self.assertEqual(moves[0]['mover'], 'black')
        self.assertEqual([move['move_number'] for move in moves], [7, 8])

    def test_multipv_and_actual_move_are_two_searches(self):
        board = chess.Board()
        move = chess.Move.from_uci('e2e4')
        engine = MagicMock(wraps=FakeEngine())
        settings = AnalysisSettings(time_limit=0.2, multipv=2)
        real, scores = analysis.analyse_movement(board, move, chess.WHITE, engine, settings)
        self.assertEqual(real[0], move)
        self.assertEqual(engine.analyse.call_count, 2)
        self.assertEqual(engine.analyse.call_args_list[0].kwargs, {'multipv': 2})
        self.assertEqual(engine.analyse.call_args_list[1].kwargs, {'root_moves': [move]})
        self.assertIn(move, [item[0] for item in scores])
        self.assertEqual(len(board.move_stack), 0)

    def test_board_restored_if_rival_search_fails(self):
        game = analysis.import_pgn('1. e4 *')
        board = game.board()
        original = board.fen()
        with patch.object(FakeEngine, 'analyse', side_effect=chess.engine.EngineError('failed')):
            with self.assertRaises(chess.engine.EngineError):
                list(analysis._iter_game(game, board, 1, Path('/unused'), False, FakeEngine(), AnalysisSettings()))
        self.assertEqual(board.fen(), original)
        self.assertEqual(board.move_stack, [])

    def test_engine_closed_on_failure_without_image_directory(self):
        game = analysis.import_pgn('1. e4 *')
        engine = MagicMock()
        engine.analyse.side_effect = chess.engine.EngineError('failed')
        manager = MagicMock()
        manager.__enter__.return_value = engine
        with patch.object(analysis, 'stockfish_path', return_value='/fake'), \
                patch.object(chess.engine.SimpleEngine, 'popen_uci', return_value=manager), \
                patch.object(Path, 'mkdir') as mkdir:
            with self.assertRaises(chess.engine.EngineError):
                analysis.analyse_game(game, game.board(), 0, 'test', create_imgs=False)
        manager.__exit__.assert_called_once()
        mkdir.assert_not_called()

    def test_settings_reject_bad_values_and_order(self):
        for values in ({'time_limit': 'nan'}, {'multipv': '2.5'}, {'excellent': '5'},
                       {'mistake': '16'}, {'time_limit': '-1'}, {'blunder': 'inf'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                AnalysisSettings.from_form(values)
        settings = AnalysisSettings.from_form({'time_limit': '1', 'multipv': '4'})
        self.assertEqual(settings.multipv, 4)
        self.assertEqual(settings.time_limit, 1)

    def test_reference_win_percent(self):
        self.assertEqual(analysis.win_percent(0), 50)
        self.assertAlmostEqual(analysis.win_percent(100), 59.1026, places=3)
        self.assertAlmostEqual(analysis.win_percent(-100), 40.8974, places=3)

    def test_thresholds_are_applied_at_boundaries(self):
        best_move, real_move = list(chess.Board().legal_moves)[:2]
        real = (real_move, 0, None)
        best = (best_move, 100, None)
        assessment, _ = analysis.movement_assessment(real, [real, best])
        self.assertEqual(assessment['category'], 'inaccuracy')
        settings = AnalysisSettings(excellent=0, inaccuracy=1, mistake=2, blunder=3)
        assessment, _ = analysis.movement_assessment(real, [real, best], settings)
        self.assertEqual(assessment['category'], 'blunder')
        # The same centipawn loss in a won position should be less significant.
        assessment, _ = analysis.movement_assessment((real_move, 1000, None), [(real_move, 1000, None), (best_move, 1100, None)])
        self.assertEqual(assessment['category'], 'excellent')

    def test_actual_move_above_candidates_does_not_get_negative_loss(self):
        first, second = list(chess.Board().legal_moves)[:2]
        assessment, _ = analysis.movement_assessment((first, 110, None), [(first, 110, None), (second, 100, None)])
        self.assertEqual(assessment['loss_cp'], 0)
        self.assertEqual(assessment['category'], 'best')

    def test_mate_messages_include_immediate_mate_and_do_not_infer_avoided(self):
        first, second = list(chess.Board().legal_moves)[:2]
        assessment, _ = analysis.movement_assessment((first, -10000, -2), [(first, -10000, -2), (second, 10000, 0)])
        self.assertIn('Mat no aprofitat', assessment['text'])
        self.assertIn('Permet un mat', assessment['text'])
        self.assertNotIn('evitat', assessment['text'])
        assessment, _ = analysis.movement_assessment((first, 10000, 0), [(first, 10000, 0), (second, 10000, 3)])
        self.assertNotIn('Mat no aprofitat', assessment['text'])

    def test_mate_slack_and_alternative_tolerance_are_used(self):
        first, second, third = list(chess.Board().legal_moves)[:3]
        real = (first, 10000, 6)
        best = (second, 10000, 2)
        assessment, _ = analysis.movement_assessment(real, [best, real], AnalysisSettings(mate_slack=2))
        self.assertIn('Manté el mat', assessment['text'])
        assessment, _ = analysis.movement_assessment(real, [best, real], AnalysisSettings(mate_slack=5))
        self.assertNotIn('Manté el mat', assessment['text'])
        _, alternatives = analysis.movement_assessment((first, 90, None), [(first, 90, None), (second, 100, None), (third, 40, None)])
        self.assertEqual([item[0] for item in alternatives], [second])

    def test_paths_rejected_before_engine_start(self):
        game = analysis.import_pgn('1. e4 *')
        for name in ('../outside', '/tmp/outside', '..', 'a\\b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                analysis.analyse_game(game, game.board(), 0, name)
        for name in ('../outside', '/outside', 'a\\b', 'C:/outside'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_target(Path('/tmp'), name)

    def test_invalid_explicit_stockfish_path_has_no_fallback(self):
        with patch.dict('os.environ', {'STOCKFISH_PATH': '/does/not/exist'}):
            with self.assertRaises(FileNotFoundError):
                stockfish_path()


class JobTests(unittest.TestCase):
    def test_progress_is_available_before_completion_and_jobs_queue(self):
        manager = JobManager()
        release = Event()
        first_published = Event()
        game = analysis.import_pgn('1. e4 e5 *')
        def stream(*args):
            yield {'index': 0, 'san': 'e4'}
            first_published.set()
            self.assertTrue(release.wait(3))
            yield {'index': 1, 'san': 'e5'}
        try:
            with patch('analysis_jobs.stream_game_analysis', side_effect=stream):
                first = manager.start(game, 0, '../partida', AnalysisSettings())
                self.assertTrue(first_published.wait(3))
                second = manager.start(game, 0, '../partida', AnalysisSettings())
                self.assertEqual(first.snapshot()['available'], 1)
                self.assertEqual(first.snapshot()['state'], 'running')
                self.assertEqual(second.snapshot()['state'], 'queued')
                self.assertNotIn('/', first.game_name)
                self.assertNotEqual(first.game_name, second.game_name)
                release.set()
                manager.executor.shutdown(wait=True)
            self.assertEqual(first.snapshot()['state'], 'complete')
            self.assertEqual(first.snapshot(1)['moves'], [{'index': 1, 'san': 'e5'}])
            self.assertIn('<svg', first.snapshot()['final_svg'])
        finally:
            release.set()
            manager.executor.shutdown(wait=True)

    def test_errors_keep_partial_results(self):
        manager = JobManager()
        game = analysis.import_pgn('1. e4 e5 *')
        def stream(*args):
            yield {'index': 0}
            raise chess.engine.EngineError('failure')
        with patch('analysis_jobs.stream_game_analysis', side_effect=stream), self.assertLogs('analysis_jobs', level='ERROR'):
            job = manager.start(game, 0, 'test', AnalysisSettings())
            manager.executor.shutdown(wait=True)
        self.assertEqual(job.snapshot()['state'], 'error')
        self.assertEqual(job.snapshot()['available'], 1)
        self.assertIsNotNone(job.snapshot()['error'])


class WebTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.manager = JobManager()
        self.patches = [patch('coachess.job_manager', self.manager),
                        patch.object(self.manager.executor, 'submit'),
                        patch('coachess.stockfish_path', return_value='/fake')]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.manager.executor.shutdown(wait=True)

    def test_empty_pgn_shows_error(self):
        response = self.client.post('/', data={'pgn': '', 'player': 'WHITE'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('PGN', response.get_data(as_text=True))

    def test_post_returns_immediately_and_poll_returns_incremental_results(self):
        response = self.client.post('/', data={'pgn': '1. e4 e5 *', 'player': 'BLACK', 'game_name': "../../foo'bar", 'multipv': '4'})
        self.assertEqual(response.status_code, 303)
        job = next(iter(self.manager.jobs.values()))
        self.assertEqual(job.settings['multipv'], 4)
        self.assertNotIn('/', job.game_name)
        response = self.client.get(response.location)
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="ca"', response.get_data(as_text=True))
        job.moves = [{'index': 0}, {'index': 1}]
        response = self.client.get(f'/api/analysis/{job.id}?since=1')
        self.assertEqual(response.json['moves'], [{'index': 1}])
        self.assertEqual(response.json['available'], 2)
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_invalid_settings_preserve_pgn(self):
        response = self.client.post('/', data={'pgn': '1. e4 *', 'blunder': '1'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('1. e4 *', response.get_data(as_text=True))
        self.assertEqual(self.manager.jobs, {})

    def test_missing_engine_shows_installation_error(self):
        with patch('coachess.stockfish_path', side_effect=FileNotFoundError('Instal·la Stockfish')):
            response = self.client.post('/', data={'pgn': '1. e4 *', 'player': 'WHITE'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Instal·la Stockfish', response.get_data(as_text=True))

    def test_unknown_job_and_bad_cursor(self):
        self.assertEqual(self.client.get('/analysis/missing').status_code, 404)
        self.client.post('/', data={'pgn': '1. e4 *'})
        job = next(iter(self.manager.jobs.values()))
        for cursor in ('oops', '-1', '2'):
            self.assertEqual(self.client.get(f'/api/analysis/{job.id}?since={cursor}').status_code, 400)


if __name__ == '__main__':
    unittest.main()
