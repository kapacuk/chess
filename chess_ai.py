# crappy AI; routinely loses
# v2 - rewinds instead of simulating boards

from copy import deepcopy
from chess_engine import parse, randint, chess12, Piece, Pawn
from numpy import array
debug = False
# from random import randint

# piece square tables- are these symmetrical? I don't think the queen is

pawnmatrix = [
    [ 0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [ 5,  5, 10, 25, 25, 10,  5,  5],
    [ 0,  0,  0, 20, 20,  0,  0,  0],
    [ 5, -5,-10,  0,  0,-10, -5,  5],
    [ 5, 10, 10,-20,-20, 10, 10,  5],
    [ 0,  0,  0,  0,  0,  0,  0,  0]]

knightmatrix = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50]]

bishopmatrix = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20]]

rookmatrix = [
    [ 0,  0,  0,  0,  0,  0,  0,  0],
    [ 5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [ 0,  0,  0,  5,  5,  0,  0,  0]]

queenmatrix = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [ -5,  0,  5,  5,  5,  5,  0, -5],
    [  0,  0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20]]

kingmatrix_early = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [ 20, 20,  0,  0,  0,  0, 20, 20],
    [ 20, 30, 10,  0,  0, 10, 30, 20]]

kingmatrix_late = [
    [-50,-40,-30,-20,-20,-30,-40,-50],
    [-30,-20,-10,  0,  0,-10,-20,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-30,  0,  0,  0,  0,-30,-30],
    [-50,-30,-30,-30,-30,-30,-30,-50]]


def reverse(matrix):
    newmatrix = []
    for i in range(1, 9):
        newmatrix.append(matrix[-i])
    return newmatrix

posvalmatrix = {
    'p': pawnmatrix,
    'R': rookmatrix,
    'Q': queenmatrix,
    'N': knightmatrix,
    'B': bishopmatrix,
    'K': kingmatrix_early
}

piecevals = {
    'p': 100,
    'R': 500,
    'Q': 900,
    'N': 295,
    'B': 305,
    'K': 5000
}

weights = {'piece_weights': piecevals, 'square_weights': posvalmatrix}


def piece_pos_value(piece):
    global posvalmatrix
    piecename = piece.display()[1]
    piecematrix = posvalmatrix[piecename]
    if piece.display()[0] == 'w':
        piecematrix = reverse(piecematrix)
    if piece.pos is None:
        return 0
    else:
        x = piece.pos[0]-1
        y = piece.pos[1]-1
    return piecematrix[y][x]


def positional_advantage(board, col):
    adv = 0
    for piece in board.pieces.values():
        if piece.col == col:
            colval = 1
        else:
            colval = -1
        adv += (piece_pos_value(piece) * colval)
        # print "%s positional bonus: %s" % (piece, (piece_pos_value(piece) * colval))
    return adv


def count_material(board, col):
    global piecevals
    val_total = 0
    for p in board.pieces.values():
        if p.col == col:
            val_total += piecevals[p.display()[1]]
    return val_total


def count_moves(board, col):
    move_total = 0
    if col == board.whose_turn:
        movelist = board.available_moves
    else:
        movelist = board.gen_all_moves(col)[0]
    for p in movelist.values():
        for m in p:
            move_total += 1
    return move_total


def count_threats(board, col):  # higher means you have more threats on the enemy
    threat_total = 0
    if col != board.whose_turn:
        movelist = board.threatened_moves
    else:
        movelist = board.gen_all_moves(col, attack_map=True)[0]
    for p in movelist.values():
        for m in p:
            threat_total += 1
    return threat_total


def check_pawns(board, col):
    pawn_files = []
    dp = 0  # doubled pawns (two pawns on one file)
    bp = 0  # blocked pawns (pawns that cannot advance directly forward)
    ip = 0  # isolated pawns (pawns without a pawn on an adjacent file)
    for p in board.pieces.values():
        if isinstance(p, Pawn) and p.col == col and p.pos is not None:
            if p.pos[0] in pawn_files:
                dp += 1
            pawn_files.append(p.pos[0])
            if p.col == 'white':
                forward_dir = array((0, 1))
            else:
                forward_dir = array((0, -1))
            infront = board.squares[tuple(array(p.pos) + forward_dir)]
            if isinstance(infront, Piece):
                bp += 1
    for f in pawn_files:
        if f-1 not in pawn_files and f+1 not in pawn_files:
            ip += 1
    return dp, bp, ip


def evaluate(board, verbose=False):
    material_weight = 1
    position_weight = 5
    # threat_weight = 1
    bp_weight, ip_weight, dp_weight = 25, 75, 50
    material_advantage = (count_material(board, 'white') - count_material(board, 'black')) * material_weight
    pos_advantage = (positional_advantage(board, 'white') - positional_advantage(board, 'black')) * position_weight
    # mobility = (count_moves(board, 'white') - count_moves(board, 'black')) * mobility_weight
    # threats = (count_threats(board, 'white') - count_threats(board, 'black')) * threat_weight
    dp, bp, ip = tuple(-array(check_pawns(board, 'white')) + array(check_pawns(board, 'black')))
    problem_pawns = sum([bp*bp_weight, ip*ip_weight, dp*dp_weight])

    if verbose:
        print "Material advantage: %s" % material_advantage
        print "Positional advantage: %s" % pos_advantage
        # print "Threat advantage: %s" % threats
        print "Doubled, blocked, isolated pawn advantage: %s, %s, %s" % (dp*dp_weight, bp*bp_weight, ip*ip_weight)
        print "Total favourability for white: %s" % sum([material_advantage, pos_advantage, problem_pawns])
    return sum([material_advantage, pos_advantage, problem_pawns])


def lookahead(board, depth=2, max_depth=2):  # simulates all possible moves for boards at an arbitrary depth
    new_movelist = {}  # here we store the moves at this depth, and the evaluation of their best outcome for us
    movelist = get_movelist(board)
    if depth > 0:
        for move in movelist:
            # print "%smoving %s from %s to %s" % (' '*depth, board.squares[move[0]], parse(move[0]), parse(move[1]))
            board.move(move[0], move[1])
            # print "move history: " + str(board.movehistory)
            if board.winner is None:  # return the value of the best move up the tree
                newboard_val = lookahead(board, depth-1, depth)  # here is the recursion
            else:  # except if the game is over, in which case return a speial value
                win_vals = {'white': 9999, 'black': -9999, 'nobody': 0}
                newboard_val = win_vals[board.winner]
            new_movelist[move] = newboard_val
            # print "%s-this position: %s" % (' '*depth, newboard_val)
            # print "%srewinding from %s to %s" % (' '*depth, parse(move[1]), parse(move[0]))
            board.rewind()

        #  get best move:
        vals = [n for n in new_movelist.values()]
        print "vals: " + str(vals)
        if board.whose_turn == 'white':
            m = max(vals)
        else:
            m = min(vals)
        bestmoves = [i for i, j in enumerate(vals) if j == m]
        bestmove = new_movelist.keys()[bestmoves[0]]
        print (" "*depth) + "best move after %s at %s to %s is: %s at %s to %s" % \
            (board.squares[board.movehistory[-1][0][1]], parse(board.movehistory[-1][0][0]),
             parse(board.movehistory[-1][0][1]), board.squares[bestmove[0]],
             parse(bestmove[0]), parse(bestmove[1]))

        if depth < max_depth:
            return evaluate(sim_move(board, (bestmove[0], bestmove[1])))

        else:
            return bestmove

    elif depth == 0:
        return evaluate(board)


def get_movelist(board):
    movelist = []
    for piece, moves in board.available_moves.iteritems():
        for movepos in moves:
            movelist.append((piece.pos, movepos))
    return movelist


def evaluate_moves(board):
    move_dict = {}
    for piece, movelist in board.available_moves.iteritems():
        for movepos in movelist:
            simboard = simulate(board)
            simboard.squares[piece.pos].move(movepos, simboard)
            move_dict[(piece.pos, movepos)] = evaluate(simboard)
    return move_dict


def best_move(board):
    col = board.whose_turn
    movedict = evaluate_moves(board)
    vals = [n for n in movedict.values()]
    if col == 'white':
        m = max(vals)
    else:
        m = min(vals)
    bestmoves = [i for i, j in enumerate(vals) if j == m]
    if len(bestmoves) == 1:
        bestmove = movedict.keys()[bestmoves[0]]
        return (bestmove[0], bestmove[1])
    else:
        bestmove = movedict.keys()[bestmoves[randint(0, len(bestmoves))]]
        return (bestmove[0], bestmove[1])


def make_best_move(board):
    # movedict = evaluate_moves(board)
    bestmove = lookahead(board)
    print "Moving %s from %s to %s" % (board.squares[bestmove[0]], parse(bestmove[0]), parse(bestmove[1]))
    board.move(bestmove[0], bestmove[1])


def simulate(board):
    simboard = deepcopy(board)
    simboard.real_game = False
    return simboard


def sim_move(board, move):  # move should be a tuple of tuples
    simboard = simulate(board)
    simboard.move(move[0], move[1])
    return simboard


def play_game():
    mainboard = chess12.Board()
    mainboard.newgame()
    while mainboard.winner is None:
        make_best_move(mainboard)
