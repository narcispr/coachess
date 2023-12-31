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

def import_pgn(pgn: str) -> chess.pgn.Game:
    pgn_io = io.StringIO(pgn)
    game = chess.pgn.read_game(pgn_io)
    return game

engine = chess.engine.SimpleEngine.popen_uci("/home/narcis/Stockfish/src/stockfish")

trp_green = "rgba(0, 255, 0, 0.5)"
trp_blue = "rgba(0, 0, 255, 0.5)"
trp_light_green = "rgba(144, 238, 144, 0.5)"
trp_orange = "rgba(255, 165, 0, 0.5)"
trp_yellow = "rgba(255, 255, 0, 0.5)"
trp_red = "rgba(255, 0, 0, 0.5)"
trp_pink = "rgba(255, 192, 203, 0.5)"
trp_cyan = "rgba(0, 255, 255, 0.5)"
trp_brown = "rgba(165, 42, 42, 0.5)"
trp_magenta = "rgba(255, 0, 255, 0.5)"
trp_gray = "rgba(128, 128, 128, 0.5)"

def get_score(info: chess.engine.InfoDict) -> int:
    # Get the evaluation in centipawns
    if info["score"].is_mate():
        mate_score = abs(info["score"].relative.moves)
        if mate_score == 0:
            mate_score = 1
        # Assign a high positive or negative value if it's a mate situation
        if info["score"].turn:
            score = 4000/mate_score
        else:
            score = -4000/mate_score
    else:
        score = info["score"].relative.score()
    return -score

def analyse_movement(board: chess.Board, move: chess.Move):
    # Analyse the performed movement
    board.push(move)
    info = engine.analyse(board, chess.engine.Limit(time=0.1))
    board.pop()
    real_score = (move, get_score(info))

    # Analyse all the possible movements
    scores = []
    for p_move in board.legal_moves:
        board.push(p_move)
        info = engine.analyse(board, chess.engine.Limit(time=0.1))
        board.pop()
        scores.append((p_move, get_score(info)))
    
    print("Real movement:", real_score, " Best movement:", max(scores, key=lambda x: x[1]))
    return real_score, scores

def display_board(board: chess.Board, arrows:list, player:int, filename:str) -> None:
    svg = chess.svg.board(board, arrows=arrows, size=400, flipped=(player==1))
    display(SVG(svg))
    # Save the SVG to a file
    if filename is not None:
        with open(filename, 'w') as f:
            f.write(svg)

def check_movement(real_score, scores):
    color = trp_red
    difference = real_score[1] - max(scores, key=lambda x: x[1])[1]
    if real_score[0] == max(scores, key=lambda x: x[1])[0]:
        text = "Best movement!!!"
        difference = 0
        color = trp_blue
    elif difference > -30:
        text = "Excellent Movement!"
        color = trp_green
    elif difference > -75:
        text = "Good Movement"
        color = trp_light_green
    elif difference > -150:
        text = "Blunder" 
        color = trp_yellow
    elif difference > -250:
        text = "Error!" 
        color = trp_orange
    else:
        text = "Big Mistake!!!"
        color = trp_red

    # get all the movements with a similar score (up to 50 points) from the best one
    similar_scores = [x for x in scores if abs(x[1] - max(scores, key=lambda x: x[1])[1]) < 50]
    # sort similar scores by the best movement
    similar_scores.sort(key=lambda x: x[1], reverse=True)
    # if real_score[0] in list of tuples similar_scores remove it. 
    alternatives = []
    for i, score in enumerate(similar_scores):
        if real_score[0] == score[0]:
            similar_scores.pop(i)
            break
        else:
            alternatives.append(score)
    return color, similar_scores, (difference, text)

def analyse_game(game: chess.pgn.Game, board: chess.Board, player:int, game_name: str) -> list:
    # Analyze all board movements
    all_scores = []
    if not os.path.exists('static/' + game_name):
        os.makedirs('static/' + game_name)
    all_info = []
    for i, move in enumerate(game.mainline_moves()):
        arrows = []
        if i >= 0 and i % 2 == player:
            real_score, scores = analyse_movement(board, move)
            color, best_movements, info = check_movement(real_score, scores)
            all_info.append(info)
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=color))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}.svg".format(game_name, i))
            for k, m in enumerate(best_movements):
                if k == 0: 
                    c=trp_magenta
                else:
                    c=trp_pink
                arrows.append(chess.svg.Arrow(m[0].from_square, m[0].to_square, color=c))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}_sol.svg".format(game_name, i))
            all_scores.append(real_score[1])  
        else:
            # Analyse the performed movement
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(time=0.1))
            board.pop()
            all_scores.append(-1*get_score(info))
            all_info.append(None)
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=trp_gray))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}.svg".format(game_name, i))
        board.push(move)
    return all_scores, all_info

def create_game_plots(all_scores, all_differences, game_name):
    # Create a new figure
    plt.figure(figsize=(10, 6))

    # Plot the scores
    clipped_scores = np.clip(all_scores, -1000, 1000)
    plt.plot(clipped_scores, color='blue', linestyle='-')
    plt.axis([0, len(clipped_scores), 0, max(clipped_scores)])

    # Add labels and title
    plt.xlabel('Move number')
    plt.ylabel('Score')
    plt.title('Game Analysis')

    # Add a grid
    plt.grid(True)

    # Show the plot
    plt.savefig("static/{}/scores.png".format(game_name), dpi=300, transparent=True)
    plt.clf()

    # Plot the differences
    a = np.clip(all_differences, -1000, 0)
    plt.plot(a, color='blue', linestyle='-')
    
    # Add labels and title
    plt.xlabel('Move number')
    plt.ylabel('Score Difference')
    plt.title('Game Analysis')

    # Add a grid
    plt.grid(True)

    # Show the plot
    plt.savefig("static/{}/differences.png".format(game_name), dpi=300, transparent=True)