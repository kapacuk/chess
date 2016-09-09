# crappy AI; routinely loses
# v2 - rewinds instead of simulating boards

from copy import deepcopy
from chess_engine2 import parse, Board, Piece, Pawn
from numpy import array
import sys
debug = False

b = Board()
b.newgame()

# piece square tables and piece values based on simplified evaluation function by Tomasz Michniewski

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
    'N': 320,
    'B': 330,
    'K': 20000
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
    for piece in board.pieces:
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
    for p in board.pieces:
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
    for p in board.pieces:
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


def evaluate(board, verbose=False, col=None, complexity = 3):
    if col is None:
        col = board.whose_turn
    if col == 'white':
        direction = 1
    else:
        direction = -1
    material_weight = 10
    position_weight = 10
    # threat_weight = 1
    bp_weight, ip_weight, dp_weight = 250, 750, 500 # millipawns

    material_advantage = (count_material(board, 'white') - count_material(board, 'black')) * material_weight
    if complexity > 1:
        pos_advantage = (positional_advantage(board, 'white') - positional_advantage(board, 'black')) * position_weight
    else:
        pos_advantage = 0
    # mobility = (count_moves(board, 'white') - count_moves(board, 'black')) * mobility_weight
    # threats = (count_threats(board, 'white') - count_threats(board, 'black')) * threat_weight
    if complexity > 2:
        dp, bp, ip = tuple(-array(check_pawns(board, 'white')) + array(check_pawns(board, 'black')))
        problem_pawns = sum([bp*bp_weight, ip*ip_weight, dp*dp_weight])
    else:
        problem_pawns = 0

    if verbose:
        print "Material advantage: %s" % (material_advantage * direction)
        if complexity > 1:
            print "Positional advantage: %s" % (pos_advantage * direction)
            # print "Threat advantage: %s" % threats
        if complexity > 2:
            print "Doubled, blocked, isolated pawn advantage: %s, %s, %s" % (dp*dp_weight*direction, bp*bp_weight*direction, ip*ip_weight*direction)
        print "Total favourability for %s: %s" % (col, (sum([material_advantage, pos_advantage, problem_pawns]) * direction))
    return sum([material_advantage, pos_advantage, problem_pawns]) * direction

def negamax(board, max_ply=2, ply=2, lastmove=None, bestmove=None):
    col = board.whose_turn
    if ply == 0:
        return (evaluate(board, 0, col, complexity=3), lastmove)
    movelist = get_movelist(board)
    print "getting %s movelist" % col
#    elif ply == 2:
#        print "trying %s to %s" % (parse(lastmove[0]), parse(lastmove[1]))
    max_score = -100000
    for move in movelist:
        print "%smoving %s from %s to %s%s" % ('-'*ply, board.squares[move[0]], parse(move[0]), parse(move[1]), "-"*(max_ply-ply))
        try:
            board.move(move[0], move[1])
        except Exception as x:
            print "Move failed (%s). The piece was %s" % (x, board.squares[move[0]])
            print "From %s to %s" % (parse(move[0]), parse(move[1]))
            print "after %s" % str(lastmove)
            print board
            sys.exit()
        score, internal_bestmove = negamax(board, max_ply, ply-1, lastmove=move, bestmove=bestmove)
        score = -score
        board.rewind()
        print "rewinding to %s's turn" % board.whose_turn
        if score > max_score:
            max_score = score
            # feed the best move down here
            if ply == max_ply:
                print "current best move: %s from %s to %s (val: %s)" % (board.squares[internal_bestmove[0]], parse(internal_bestmove[0]), parse(internal_bestmove[1]), score)
                bestmove = internal_bestmove
            else:
                bestmove = lastmove





    return (max_score, bestmove)
    #return max_score



def get_movelist(board):
    movelist = []
    for piece_pos, moves in board.available_moves.iteritems():
        for movepos in moves:
            movelist.append((piece_pos, movepos))
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
    simboard = deepcopy(board)
    bestmove = negamax(simboard)[1]
    print "Moving %s from %s to %s" % (board.squares[bestmove[0]], parse(bestmove[0]), parse(bestmove[1]))
    board.move(bestmove[0], bestmove[1])
    print board


def simulate(board):
    simboard = deepcopy(board)
    simboard.real_game = False
    return simboard


def sim_move(board, move):  # move should be a tuple of tuples
    simboard = simulate(board)
    simboard.move(move[0], move[1])
    return simboard


def play_game():
    mainboard = Board()
    mainboard.newgame()
    while mainboard.winner is None:
        make_best_move(mainboard)



### testing promotion, promotion rewind
#b.play('e4')
#b.play('d5')
#b.play('exd5')
#b.play('c6')
#b.play('dxc6')
#b.play('h6')
#b.play('cxb7')
#b.play('Na6')
#b.play('bxc8=Q')
#b.rewind()

# testing checkmate??

b.play('d4')
b.play('c5')
b.play('Nc3')
b.play('h6')
b.play('Nb5')
b.play('h5')
b.play('Nxa7')
b.play('h4')
b.play('Nc6')
b.play('Qa5')
b.play('Nxa5')
b.play('Rxa5')
b.play('dxc5')
make_best_move(b)