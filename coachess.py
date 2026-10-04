import os
import secrets
from dataclasses import asdict

from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, abort

from analysis_jobs import JobManager
from analysis_settings import AnalysisSettings, CONTROLS
from chess_analysis import import_pgn
from stockfish_config import stockfish_path

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
job_manager = JobManager()


def render_home(status=200):
    defaults = asdict(AnalysisSettings())
    values = {name: request.form.get(name, value) for name, value in defaults.items()}
    return render_template('index.html', controls=CONTROLS, values=values, defaults=defaults), status


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            game = import_pgn(request.form.get('pgn', ''))
            player_name = request.form.get('player', 'WHITE')
            if player_name not in ('WHITE', 'BLACK'):
                raise ValueError("Selecciona blanques o negres.")
            settings = AnalysisSettings.from_form(request.form)
            stockfish_path()
        except ValueError as exc:
            flash(str(exc))
            return render_home(400)
        except OSError as exc:
            flash(str(exc))
            return render_home(503)
        job = job_manager.start(
            game, 0 if player_name == 'WHITE' else 1,
            request.form.get('game_name', '').strip()[:120], settings,
        )
        return redirect(url_for('results', job_id=job.id), code=303)
    return render_home()


def get_job(job_id):
    job = job_manager.get(job_id)
    if job is None:
        abort(404)
    return job


@app.get('/analysis/<job_id>')
def results(job_id):
    job = get_job(job_id)
    return render_template(
        'show_results.html', job=job.snapshot(),
        status_url=url_for('analysis_status', job_id=job_id),
        image_base=url_for('static', filename=job.game_name) + '/',
    )


@app.get('/api/analysis/<job_id>')
def analysis_status(job_id):
    job = get_job(job_id)
    try:
        since = int(request.args.get('since', 0))
    except ValueError:
        return jsonify(error="El punt d'inici ha de ser un nombre enter."), 400
    if not 0 <= since <= job.total:
        return jsonify(error="El punt d'inici és fora de la partida."), 400
    response = jsonify(job.snapshot(since))
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.errorhandler(404)
def not_found(error):
    return render_template('not_found.html'), 404


if __name__ == '__main__':
    app.run()
