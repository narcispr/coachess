import chess.pgn
import chess.svg
import chess.engine
import copy
import io
from IPython.display import SVG, display
from matplotlib import pyplot as plt
import numpy as np
import seaborn as sns
import os

from flask import Flask, render_template, request, flash
from chess_analysis import import_pgn, analyse_game, create_game_plots

app = Flask(__name__)
app.secret_key = 'bon_2024'

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        pgn = request.form.get('pgn')
        player_name = request.form.get('player')
        player = 0
        if player_name == "BLACK":
            player = 1
        print("player", player, type(player))
        game_name = request.form.get('game_name')
        print("game_name", game_name, type(game_name))
        game = import_pgn(pgn)
        total_moves = sum(1 for _ in game.mainline_moves())
        print("Total moves:", total_moves)
        board = game.board()
        message = 'The game is going to be analyzed. {} turns to go. Be pattient!!!'.format(total_moves)
        print(message)
        flash(message)
        all_scores, all_info = analyse_game(game, board, player, game_name)
        all_scores = np.clip(all_scores, -1500, 1500).tolist()
        # create_game_plots(all_scores, all_differences, game_name)
        return render_template('show_results.html', game_name=game_name, total_moves=total_moves, player=player, info=all_info, all_scores=all_scores)
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)