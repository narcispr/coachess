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

def get_score(info: chess.engine.InfoDict, color: chess.Color) -> int:
    score = info["score"].pov(color).score(mate_score=10000)
    if info["score"].is_mate():
        mate = info["score"].pov(color).mate()
    else:
        mate = None
    return score, mate
   
def analyse_movement(board: chess.Board, move: chess.Move, color: chess.Color):
    # Analyse all the possible movements
    scores = []
    for p_move in board.legal_moves:
        board.push(p_move)
        info = engine.analyse(board, chess.engine.Limit(time=0.1))
        board.pop()
        
        # Get the score
        if p_move == move:
            s, m = get_score(info, color)
            real_score = (move, s, m)
            scores.append(real_score)
        else:
            s, m = get_score(info, color)
            scores.append((p_move, s, m))
        
    print("Real movement:", real_score, " Best movement:", max(scores, key=lambda x: x[1]))
    return real_score, scores

def display_board(board: chess.Board, arrows:list, player:int, filename:str, create_imgs: bool) -> None:
    svg = chess.svg.board(board, arrows=arrows, size=450, flipped=(player==1))
    display(SVG(svg))
    # Save the SVG to a file
    if filename is not None and create_imgs:
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

    avoid_checkmate = 0
    missing_mate = 100

    for m in scores:
        if m[2] is not None:
            if m[2] < 0:
                avoid_checkmate += 1 # if all movements except 1 or 2 are checkmate... it is considered a checkmate avoided
            elif m[2] > 0:
                missing_mate = min(missing_mate, m[2])
    
    if missing_mate < 100 and (real_score[2] is None or real_score[2] > missing_mate):
        text += " Missed mate in {}".format(missing_mate)
        print(text)
    if avoid_checkmate > len(scores)/2 and (real_score[2] is None or real_score[2] < 0):
        text += " Possible checkmate avoided!"
        print(text)

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
    print(text)
    return color, similar_scores, (difference, text)

def analyse_game(game: chess.pgn.Game, board: chess.Board, player:int, game_name: str, create_imgs: bool=True) -> list:
    if player == 0:
        color = chess.WHITE
    else:
        color = chess.BLACK
    
    # Analyze all board movements
    all_scores = []
    all_info = []
    all_moves = []

    if not os.path.exists('static/' + game_name):
        os.makedirs('static/' + game_name)
    
    for i, move in enumerate(game.mainline_moves()):
        all_moves.append(move.uci())
        arrows = []
        if i >= 0 and i % 2 == player:
            real_score, scores = analyse_movement(board, move, color)
            color, best_movements, info = check_movement(real_score, scores)
            all_info.append(info)
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=color))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}.svg".format(game_name, i), create_imgs=create_imgs)
            for k, m in enumerate(best_movements):
                if k == 0: 
                    c=trp_magenta
                else:
                    c=trp_pink
                arrows.append(chess.svg.Arrow(m[0].from_square, m[0].to_square, color=c))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}_sol.svg".format(game_name, i), create_imgs=create_imgs)
            all_scores.append(real_score[1])  
        else:
            # Analyse the rival movement
            board.push(move)
            info = engine.analyse(board, chess.engine.Limit(time=0.1))
            board.pop()
            s, _ = get_score(info, color)
            all_scores.append(-s)
            all_info.append(None)
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color=trp_gray))
            display_board(board, arrows, player, filename="static/{}/move_{:03d}.svg".format(game_name, i), create_imgs=create_imgs)
        board.push(move)

    return all_scores, all_info, all_moves
