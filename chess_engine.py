#!/usr/bin/env python
# -*- coding: utf-8 -*-

# version 15 - experimental 'rewind' function

# check the check code to see if special moves can allow you to escape check


# to do:
#   board history, FEN representation (working on it)
#   gui? (done)

from numpy import array  # for move generation vector arithmetic
import sys
import json

debug = False

# interface functions:


def gui_process(jsonstring):
    sys.stderr.write('receiving json string: %s' % jsonstring)
    global mainboard
    jsondict = json.loads(jsonstring)
    command = jsondict[u'command']
    if command == u'getMoves':
        pos_tuple = (int(jsondict['piecePos'][0]), int(jsondict['piecePos'][1]))
        # piece = mainboard.squares[pos_tuple]
        gui_sendmoves(mainboard, pos_tuple)
    elif command == u'sendMove':
        oldpos = (int(jsondict[u'piecePos'][0]), int(jsondict[u'piecePos'][1]))
        newpos = (int(jsondict[u'newPos'][0]), int(jsondict[u'newPos'][1]))
        # sys.stderr.write(str(oldpos) + str(newpos))
        if isinstance(mainboard.squares[oldpos], Pawn) and (newpos[1] == 8 or newpos[1] == 1):
            gui_askpromotion()  # special case of pawn promotion
        mainboard.move(oldpos, newpos)
        gui_sendboard(mainboard)
    elif command == u'newGame':
        mainboard = Board()
        mainboard.newgame()
        gui_sendboard(mainboard)


def gui_sendboard(boardstate):
    newdict = {}
    for key, value in boardstate.squares.iteritems():
        newdict[str(key[0]) + str(key[1])] = str(value)
    if boardstate.winner is None:
        jsonout = {'message': 'boardState', 'board': newdict, 'turn': boardstate.whose_turn, 'winner': 'None'}
    else:
        jsonout = {'message': 'boardState', 'board': newdict, 'turn': boardstate.whose_turn, 'winner': boardstate.winner}
    jsonstring = json.dumps(jsonout) + "\n"
    # sys.stderr.write(jsonstring)
    sys.stdout.write(jsonstring)
    sys.stdout.flush()


def gui_sendmoves(board_obj, piece_pos):
    newlist = []
    piece = board_obj.squares[piece_pos]
    moves = board_obj.available_moves[piece]
    for move in moves:
        newlist.append(str(move[0])+str(move[1]))
    jsonout = {'message': 'pieceMoves', 'piecePos': str(piece_pos[0]) + str(piece_pos[1]), 'moves': newlist}
    jsonstring = json.dumps(jsonout) + "\n"
    sys.stdout.write(jsonstring)
    sys.stdout.flush()


def gui_askpromotion():
    # send event to gui to pick a piece?
    pass


# auxiliary functions:

# turns rank/file notation (e.g. 'e4') into tuple coordinates, or vice versa.
# for user friendliness, doesn't need optimisation
def parse(coord):
    if isinstance(coord, str):
        letter = ord(coord[0]) - 96
        number = int(coord[1])
        return (letter, number)
    elif isinstance(coord, tuple):
        x = chr(coord[0] + 96)
        y = str(coord[1])
        return (x+y)
    elif isinstance(coord, list):
        outlist = []
        for element in coord:
            outlist.append(parse(element))
        return outlist


def opposite(col):  # i know this is a weird function, deal with it
    if col == 'white':
        return 'black'
    elif col == 'black':
        return 'white'


def turnsign(col):
    if col == 'white':
        return 1
    elif col == 'black':
        return -1


def get_vector(target, origin):  # takes two position tuples as input - returns the squares in between them
    vector_diff = array(target) - array(origin)
    vector_dist = max(abs(vector_diff))
    vector_unit = vector_diff / vector_dist
    vector_squares = []  # vector of positions in between two positions (inclusive of the origin)
    for i in range(0, vector_dist):
        vector_squares.append(tuple(origin + (vector_unit * i)))
    return vector_squares


# core engine classes:

class Piece(object):
    # this method might not be strictly necessary; or might be moved to a user-only move function,
    # since the AI will already know which moves are legal
    def is_pseudolegal(self, newpos, board_obj):
        if board_obj.winner is not None:
            board_obj.playermessage("This game is over. The winner is %s" % board_obj.winner)
            return False
        else:
            log("Can %s move from %s to %s?" % (self, parse(self.pos), parse(newpos)))
            # print self
            piece_movelist = board_obj.available_moves[self]
            if newpos in piece_movelist:
                log("Yes it can")
                specmoves = [n[0] for n in board_obj.available_specials[self]]
                if newpos in specmoves:
                    log("And it is a special move")
                    return True
                else:
                    log("And it is a normal move")
                    return True
            else:
                log("No it cannot")
                return False

    def move(self, newpos, board_obj, force=False):
        log("Checking move legality")
        if self.is_pseudolegal(newpos, board_obj) or force:
            # self.has_moved = True
            if not isinstance(board_obj.squares[newpos], Piece):  # simple move
                board_obj.movehistory.append(((self.pos, newpos), 'move'))
                log("Handling simple move by %s" % self.display())
                board_obj.squares[self.pos] = None
                self.pos = newpos
                board_obj.squares[self.pos] = self
                board_obj.advance_turn()
                if isinstance(self, Pawn):
                    board_obj.halfmove_clock = 0  # reset 50-turn clock if pawn moves
            else:  # capture move
                board_obj.movehistory.append(((self.pos, newpos), 'capture'))
                target = board_obj.squares[newpos]
                log("Handling %s capture by %s" % (target.display(), self.display()))
                target.remove(board_obj)
                board_obj.squares[newpos] = self
                board_obj.squares[self.pos] = None
                self.pos = newpos
                board_obj.advance_turn()
                board_obj.halfmove_clock = 0  # reset 50-turn clock if piece is captured
        else:
            board_obj.playermessage("Illegal move")

    def remove(self, board_obj):
        log("Removing %s" % self.display())
        board_obj.squares[self.pos] = None
        self.pos = None
        if board_obj.real_game:
            board_obj.deadpieces.append(self)
            for key in board_obj.pieces:  # possibly a hack - find self in the board pieces array
                if board_obj.pieces[key] == self:
                    del board_obj.pieces[key]
                    break

    def display(self):
        return('%s%s' % (self.col[0], self.symbol))

    def __str__(self):
        return self.display()


class SlidingPiece(Piece):  # bishops and rooks and queens
    def gen_moves(self, board_obj, attack_map=False):  # also detects pins
        log("Generating moves for %s at %s" % (self, parse(self.pos)))
        possible_moves = []      # a list of positional tuples for this piece, of the form [(x,y), (x,y)], etc
        possible_captures = []
        for direction in self.moveset:
            newpos = array(self.pos)
            while True:
                newpos = newpos + direction
                if (not 1 <= newpos[0] <= 8) or (not 1 <= newpos[1] <= 8):  # check if within board
                    break
                elif not isinstance(board_obj.squares[tuple(newpos)], Piece):  # valid move
                    possible_moves.append(tuple(newpos))
                elif board_obj.squares[tuple(newpos)].col == self.col:  # blocked by friendly piece
                    if attack_map:
                        possible_moves.append(tuple(newpos))  # counts as threatened, but not a move
                        break
                    else:
                        break
                else:    # enemy piece; so, valid capture
                    possible_captures.append(tuple(newpos))
                    # if we are checking a king, we have to threaten the square behind him
                    if isinstance(board_obj.squares[tuple(newpos)], King) and attack_map:
                        newpos = newpos + direction
                        if (1 <= newpos[0] <= 8) and (1 <= newpos[1] <= 8):
                            possible_moves.append(tuple(newpos))
                    else:
                        potentially_pinned_piece = board_obj.squares[tuple(newpos)]
                        while attack_map:  # keep going and look for enemy king - if found, this is a pin
                            newpos = newpos + direction
                            if (not 1 <= newpos[0] <= 8) or (not 1 <= newpos[1] <= 8):  # check if within board
                                break
                            elif isinstance(board_obj.squares[tuple(newpos)], Piece):  # if it's a piece
                                target = board_obj.squares[tuple(newpos)]
                                if isinstance(target, King):  # and it is a king
                                    if target.col != self.col:  # and it is the enemy king
                                        log("Pin detected on %s at %s" %
                                            (potentially_pinned_piece, parse(potentially_pinned_piece.pos)))  # it is a pin
                                        board_obj.pinned_pieces[potentially_pinned_piece] = get_vector(target.pos, self.pos)
                                        break
                                else:  # otherwise it is a piece that is not the enemy king, so stop looking
                                    break
                    break
        return possible_moves + possible_captures, []  # the [] is possible special moves, but sliding pieces don't have any


class Rook(SlidingPiece):
    def __init__(self, col, pos):
        self.col = col
        self.pos = pos
        self.val = 5
        self.has_moved = False
        self.moveset = [array([0, 1]), array([1, 0]), array([0, -1]), array([-1, 0])]
        self.symbol = 'R'
        if self.col == 'white':
            self.fensymbol = 'R'
        else:
            self.fensymbol = 'r'
        self.filename = 'Chess_%srook.png' % col[0]


class Knight(Piece):
    def __init__(self, col, pos):
        self.col = col
        self.pos = pos
        self.val = 3
        self.has_moved = False
        self.moveset = [array([2, 1]), array([1, 2]), array([2, -1]), array([-1, 2]),
                        array([-2, 1]), array([1, -2]), array([-2, -1]), array([-1, -2])]
        self.symbol = 'N'
        if self.col == 'white':
            self.fensymbol = 'N'
        else:
            self.fensymbol = 'n'
        self.filename = 'Chess_%sknight.png' % col[0]

    def gen_moves(self, board_obj, attack_map=False):  # knight moves are different, so this replaces the method in the Piece class
        log("Generating moves for %s at %s" % (self, parse(self.pos)))
        possible_moves = []
        possible_captures = []
        for direction in self.moveset:
            newpos = array(self.pos) + direction
            if (not 1 <= newpos[0] <= 8) or (not 1 <= newpos[1] <= 8):  # check if within board
                pass
            elif not isinstance(board_obj.squares[tuple(newpos)], Piece):  # valid move
                possible_moves.append(tuple(newpos))
            elif board_obj.squares[tuple(newpos)].col == self.col:  # blocked by friendly piece
                if attack_map:
                    # this shows that friendly piece as threatened for purpose of attack maps - i.e. check resolution
                    possible_moves.append(tuple(newpos))
            else:    # valid capture
                possible_captures.append(tuple(newpos))
        return possible_moves + possible_captures, []  # the [] is possible special moves, but knights don't have any


class Bishop(SlidingPiece):
    def __init__(self, col, pos):
        self.col = col
        self.pos = pos
        self.val = 3
        self.has_moved = False
        self.moveset = [array([1, 1]), array([1, -1]), array([-1, -1]), array([-1, 1])]
        self.symbol = 'B'
        if self.col == 'white':
            self.fensymbol = 'B'
        else:
            self.fensymbol = 'b'
        self.filename = 'Chess_%sbishop.png' % col[0]


class King(Piece):
    def __init__(self, col, pos):
        # print "initialising %s king" % col
        self.col = col
        self.pos = pos
        self.val = 50
        self.has_moved = False
        self.moveset = [array([0, 1]), array([1, 1]), array([1, 0]), array([1, -1]),
                        array([0, -1]), array([-1, -1]), array([-1, 0]), array([-1, 1])]
        self.symbol = 'K'
        if self.col == 'white':
            self.fensymbol = 'K'
        else:
            self.fensymbol = 'k'
        self.filename = 'Chess_%sking.png' % col[0]

    def gen_moves(self, board_obj, attack_map=False):  # same code as the knight move
        log("Generating moves for %s at %s" % (self, parse(self.pos)))
        possible_moves = []
        possible_captures = []
        possible_specials = []
        threatened_squares = [item for sublist in board_obj.threatened_moves.values() for item in sublist]
        for direction in self.moveset:
            newpos = array(self.pos) + direction
            if (not 1 <= newpos[0] <= 8) or (not 1 <= newpos[1] <= 8):  # check if within board
                pass
            elif tuple(newpos) not in threatened_squares:
                if not isinstance(board_obj.squares[tuple(newpos)], Piece):  # valid move
                    possible_moves.append(tuple(newpos))
                elif board_obj.squares[tuple(newpos)].col == self.col:  # blocked by friendly piece
                    if attack_map:
                            possible_moves.append(tuple(newpos))
                else:    # valid capture
                    possible_captures.append(tuple(newpos))
        # castling:
        if not(self.has_moved or board_obj.check):
            if self.col == 'white':
                qrook = board_obj.squares[(1, 1)]
                krook = board_obj.squares[(8, 1)]
            else:
                qrook = board_obj.squares[(1, 8)]
                krook = board_obj.squares[(8, 8)]
            # collapse list of lists:
            # threatened_squares = [item for sublist in board_obj.threatened_moves.values() for item in sublist]
            if isinstance(qrook, Rook) and not qrook.has_moved:
                intervening_files = [array((4, 0)), array((3, 0)), array((2, 0))]
                intervening_squares = intervening_files + array((0, self.pos[1]))
                validity = 1
                for square in intervening_squares:  # if all intervening squares are empty, and not under threat
                    if board_obj.squares[tuple(square)] is not None:
                        validity -= 1
                    elif (tuple(square) in [tuple(s) for s in threatened_squares]):
                        if (tuple(square) in [tuple(s) for s in intervening_squares[0:2]]):
                            validity -= 1
                if validity == 1:
                    possible_moves.append((self.pos[0]-2, self.pos[1]))
                    possible_specials.append([(self.pos[0]-2, self.pos[1]), 'qside'])
            if isinstance(krook, Rook) and not krook.has_moved:
                intervening_files = [array((6, 0)), array((7, 0))]
                intervening_squares = intervening_files + array((0, self.pos[1]))
                validity = 1
                for square in intervening_squares:  # if all intervening squares are empty, and not under threat
                    if board_obj.squares[tuple(square)] is not None:
                        validity -= 1
                    elif (tuple(square) in [tuple(s) for s in threatened_squares]):
                        validity -= 1
                if validity == 1:
                    possible_moves.append((self.pos[0]+2, self.pos[1]))
                    possible_specials.append([(self.pos[0]+2, self.pos[1]), 'kside'])
        return possible_moves + possible_captures, possible_specials

    def castle(self, side, board_obj, force=False):
        if side == 'kside':
            k_dist = array((2, 0))
            r_pos = array(self.pos) + array((3, 0))
            r_dist = array((-2, 0))
            rook = board_obj.squares[tuple(r_pos)]
        else:
            k_dist = array((-2, 0))
            r_pos = array(self.pos) + array((-4, 0))
            r_dist = array((3, 0))
            rook = board_obj.squares[tuple(r_pos)]
        r_new_pos = r_pos + r_dist
        k_new_pos = tuple(array(self.pos) + k_dist)
        if self.is_pseudolegal(k_new_pos, board_obj) or force:
            board_obj.movehistory.append(((self.pos, k_new_pos), side))
            board_obj.squares[tuple(rook.pos)] = None
            board_obj.squares[tuple(r_new_pos)] = rook
            rook.pos = tuple(r_new_pos)
            board_obj.squares[tuple(self.pos)] = None
            board_obj.squares[tuple(k_new_pos)] = self
            self.pos = tuple(k_new_pos)
            self.has_moved = True
            rook.has_moved = True
            board_obj.advance_turn()
        else:
            board_obj.playermessage("Illegal move")


class Queen(SlidingPiece):
    def __init__(self, col, pos):
        self.col = col
        self.pos = pos
        self.val = 9
        self.has_moved = False
        self.moveset = [array([0, 1]), array([1, 1]), array([1, 0]), array([1, -1]),
                        array([0, -1]), array([-1, -1]), array([-1, 0]), array([-1, 1])]
        self.symbol = 'Q'
        if self.col == 'white':
            self.fensymbol = 'Q'
        else:
            self.fensymbol = 'q'
        self.filename = 'Chess_%squeen.png' % col[0]


class Pawn(Piece):
    def __init__(self, col, pos):
        self.col = col
        self.pos = pos
        self.val = 1
        # self.has_moved = False
        self.symbol = 'p'
        self.captureset = [array([1, 0]), array([-1, 0])]
        self.movedir = array([0, turnsign(self.col)])  # +1 for white, -1 for black
        if self.col == 'white':
            self.fensymbol = 'P'
            self.homerow = 2
        elif self.col == 'black':
            # self.movedir = array([0, -1])
            self.fensymbol = 'p'
            self.homerow = 7
        self.filename = 'Chess_%spawn.png' % col[0]

    def gen_moves(self, board_obj, attack_map=False):  # pawn move function
        log("Generating moves for %s at %s" % (self, parse(self.pos)))
        possible_moves = []
        possible_captures = []
        possible_specials = []
        promotable = False
        if (self.col == 'white' and self.pos[1] == 7) or (self.col == 'black' and self.pos[1] == 2):
            promotable = True
        moveset = [array(self.pos) + self.movedir]
        # by design, the pawn's forward move does not check for board boundaries
        # if this triggers a KeyError, something's gone wrong
        if self.pos[1] == self.homerow:  # double move if we can
            newpos = array(self.pos) + self.movedir*2
            moveset.append(newpos)
            possible_specials.append([tuple(newpos), 'pawndouble'])
        for move in moveset:  # check for straightorward moves
            if not isinstance(board_obj.squares[tuple(move)], Piece):  # valid move
                if not attack_map:
                    # does not consider places that pawns can move to be 'threatened' squares according to attack map
                    possible_moves.append(tuple(move))
                    if promotable:
                        possible_specials.append([tuple(move), 'promotion'])
        diagonals = array([array([1, 1]), array([-1, 1])]) * array([1, self.movedir[1]])
        for diagmove in diagonals:  # check for diagonal captures
            newpos = array(self.pos) + diagmove
            if (1 <= newpos[0] <= 8) and (1 <= newpos[1] <= 8):
                target = board_obj.squares[tuple(newpos)]
                if attack_map:
                    possible_moves.append(tuple(newpos))
                else:
                    # print "newpos is %s and board_obj.enpassant is %s" % (str(tuple(newpos)), str(board_obj.enpassant))
                    # print "board_obj.enpassant_clock is %s" % board_obj.enpassant_clock
                    if tuple(newpos) == board_obj.enpassant and board_obj.enpassant_clock == 2:
                        # print("En passant detected on square %s" % parse(newpos))
                        possible_captures.append(tuple(newpos))  # can catch en passant
                        possible_specials.append([tuple(newpos), 'enpassant'])
                    elif isinstance(target, Piece) and target.col == opposite(self.col):
                        possible_captures.append(tuple(newpos))  # enemy piece on diagonal
                        if promotable:
                            possible_specials.append([tuple(newpos), 'promocapture'])
                    # else:
                    #     if attack_map == True:  # this square cannot be entered or captured by enemy king
                    #         possible_moves.append(tuple(newpos))
        return possible_moves + possible_captures, possible_specials

    def double_move(self, new_pos, board_obj):
        if self.is_pseudolegal(new_pos, board_obj):
            if self.col == 'white':
                movedir = array((0, 1))
            else:
                movedir = array((0, -1))
            skipped_square = tuple(array(self.pos) + movedir)
            board_obj.squares[self.pos] = None
            board_obj.squares[new_pos] = self
            # board_obj.squares[skipped_square] = enPassantSquare(skipped_square, board_obj, self)
            board_obj.enpassant = skipped_square
            board_obj.enpassant_clock = 2
            board_obj.movehistory.append(((self.pos, new_pos), 'pawndouble'))
            self.pos = new_pos
            self.has_moved = True
            board_obj.advance_turn()
        else:
            board_obj.playermessage("Illegal move")

    def en_passant(self, square, board_obj):
        if self.is_pseudolegal(square, board_obj):
            board_obj.movehistory.append(((self.pos, square), 'enpassant'))
            if self.col == 'white':
                attackdir = array((0, 1))
            else:
                attackdir = array((0, -1))
            diag = array(square) - array(self.pos)
            captured_pawn = board_obj.squares[tuple(array(self.pos) + (diag - attackdir))]
            captured_pawn.remove(board_obj)
            board_obj.squares[self.pos] = None
            self.pos = square
            board_obj.squares[square] = self
            board_obj.advance_turn()
        else:
            board_obj.playermessage("Illegal move")

    def promote(self, new_pos, piece_class, board_obj):
        if self.is_pseudolegal(new_pos, board_obj):
            for key, value in board_obj.pieces.iteritems():  # possibly a hack - find self in the board pieces array
                if board_obj.pieces[key] == self:
                    board_obj.squares[self.pos] = None
                    self = piece_class(self.col, self.pos)
                    if board_obj.squares[new_pos] is not None:
                        board_obj.squares[new_pos].remove(board_obj)
                    board_obj.squares[new_pos] = self
                    board_obj.movehistory.append((self.pos, new_pos), 'promotion')
                    self.pos = new_pos
                    board_obj.pieces[key] = self
                    board_obj.advance_turn()
                    break
            # self.move(new_pos, board_obj, force=True)
        else:
            board_obj.playermessage("Illegal move")


class Board(object):
    def newgame(self):
        piecenames = ['w_q_rook', 'w_q_knight', 'w_q_bishop', 'w_queen', 'w_king', 'w_k_bishop',
                      'w_k_knight', 'w_k_rook', 'b_q_rook', 'b_q_knight', 'b_q_bishop', 'b_queen',
                      'b_king', 'b_k_bishop', 'b_k_knight', 'b_k_rook', 'w_a_pawn', 'w_b_pawn',
                      'w_c_pawn', 'w_d_pawn', 'w_e_pawn', 'w_f_pawn', 'w_g_pawn', 'w_h_pawn',
                      'b_a_pawn', 'b_b_pawn', 'b_c_pawn', 'b_d_pawn', 'b_e_pawn', 'b_f_pawn',
                      'b_g_pawn', 'b_h_pawn']
        self.pieces = {piecenames[0]: Rook('white', (1, 1)),
                       piecenames[1]: Knight('white', (2, 1)),
                       piecenames[2]: Bishop('white', (3, 1)),
                       piecenames[3]: Queen('white', (4, 1)),
                       piecenames[4]: King('white', (5, 1)),
                       piecenames[5]: Bishop('white', (6, 1)),
                       piecenames[6]: Knight('white', (7, 1)),
                       piecenames[7]: Rook('white', (8, 1)),
                       piecenames[8]: Rook('black', (1, 8)),
                       piecenames[9]: Knight('black', (2, 8)),
                       piecenames[10]: Bishop('black', (3, 8)),
                       piecenames[11]: Queen('black', (4, 8)),
                       piecenames[12]: King('black', (5, 8)),
                       piecenames[13]: Bishop('black', (6, 8)),
                       piecenames[14]: Knight('black', (7, 8)),
                       piecenames[15]: Rook('black', (8, 8)),
                       piecenames[16]: Pawn('white', (1, 2)),
                       piecenames[17]: Pawn('white', (2, 2)),
                       piecenames[18]: Pawn('white', (3, 2)),
                       piecenames[19]: Pawn('white', (4, 2)),
                       piecenames[20]: Pawn('white', (5, 2)),
                       piecenames[21]: Pawn('white', (6, 2)),
                       piecenames[22]: Pawn('white', (7, 2)),
                       piecenames[23]: Pawn('white', (8, 2)),
                       piecenames[24]: Pawn('black', (1, 7)),
                       piecenames[25]: Pawn('black', (2, 7)),
                       piecenames[26]: Pawn('black', (3, 7)),
                       piecenames[27]: Pawn('black', (4, 7)),
                       piecenames[28]: Pawn('black', (5, 7)),
                       piecenames[29]: Pawn('black', (6, 7)),
                       piecenames[30]: Pawn('black', (7, 7)),
                       piecenames[31]: Pawn('black', (8, 7))}
        self.squares = {}
        for p in self.pieces:
            self.squares[self.pieces[p].pos] = self.pieces[p]
        for x in range(1, 9):
            for y in range(1, 9):
                if (x, y) not in self.squares:
                    self.squares[(x, y)] = None
        self.whose_turn = 'white'
        self.check = False
        self.checking_piece = None  # only a single piece, but it shouldn't be referred to if in double check
        self.pinned_pieces = {}  # pinned_pieces should be a dict with the piece as they key, and the vector of the pin as values
        self.winner = None
        # declaring this now is a hack because the gen moves function below checks threatened moves for castling availability:
        self.threatened_moves = {}
        self.enpassant = None
        self.enpassant_clock = 0
        # dict of piece objects linked to the list of moves those pieces are able to take
        # specials take the form: {king_object: [(x,y), 'qside_castle']}
        self.available_moves, self.available_specials = self.gen_all_moves('white')
        self.threatened_moves, self.threatened_specials = self.gen_all_moves('black', attack_map=True)
        self.turn = 1
        self.halfmove_clock = 0
        self.halfmove_history = [0]
        self.deadpieces = []
        self.movehistory = []
        self.real_game = True    # this is False for simulated board states
        self.playermessage(self.display(self.whose_turn))

    def gen_all_moves(self, col, attack_map=False):  # need to prune this if you are in check (or all the time?)
        log("Generating new list of moves for %s" % col)
        all_moves = {}  # a dict of piece names, and their moves
        all_specials = {}
        for piece_name, piece_obj in self.pieces.iteritems():
            if piece_obj.col == col and piece_obj.pos is not None:  # only pieces of the given colour
                # print piece_obj
                piece_moves, piece_specials = piece_obj.gen_moves(self, attack_map)
                all_moves[piece_obj] = piece_moves
                all_specials[piece_obj] = piece_specials
        return all_moves, all_specials

    def gen_checked_moves(self, col):
        # 3 possible ways to resolve check:
        # capture the checking piece (if single check)
        # interpose a piece on the attack vector (if single check, and only if checking piece is a slider)
        # move king out of a threatened square (the only option when in double check)
        pseudolegal_moves, pseudolegal_specials = self.gen_all_moves(col, attack_map=False)
        legal_moves = {}

        # calculate attack vector - this will be messy code
        if col == 'white':  # this is a stupid way of doing it, but i can't think of a better way without tearing up everything
            checked_king = self.pieces['w_king']
        else:
            checked_king = self.pieces['b_king']

        if isinstance(self.checking_piece, SlidingPiece):
            attack_vector = get_vector(checked_king.pos, self.checking_piece.pos)  # vector of positions between king and checker
        else:
            attack_vector = []
        threatened_squares = [item for sublist in self.threatened_moves.values() for item in sublist]  # collapse list of lists
        for piece, pmoves in pseudolegal_moves.iteritems():
            newmoves = []
            for move in pmoves:
                # capture checking piece - can't do this in double check:
                if self.squares[move] == self.checking_piece and self.check == 1:
                    newmoves.append(move)
                # interpose piece on attack vector, and become pinned - can't do this in double check
                elif move in attack_vector and self.check == 1 and not isinstance(piece, King):
                    newmoves.append(move)
                    self.pinned_pieces[piece] = attack_vector
                elif isinstance(piece, King) and move not in threatened_squares:  # move king into safe square
                    newmoves.append(move)  # done???
            legal_moves[piece] = newmoves
        return legal_moves, pseudolegal_specials

#   def prune_all_moves(self, movelist): # used when your king is in check - checks all moves to see if they leave you in check
#       log("Pruning movelist")
#       pruned_moves = {} # create a new dict for valid moves in check
#       pass
#       return pruned_moves

    def display(self, view='white'):
        if view == 'black':
            boardrange = [range(1, 9), range(8, 0, -1)]
            files = "h  g  f  e  d  c  b  a"
        elif view == 'white':
            boardrange = [range(8, 0, -1), range(1, 9)]
            files = "a  b  c  d  e  f  g  h"
        out_string = str()
        out_string += """    %s
  +-------------------------+\n""" % files
        for y in boardrange[0]:
            out_string += '%s | ' % y
            for x in boardrange[1]:
                if self.squares[(x, y)] is not None:
                    out_string += self.squares[(x, y)].display()
                else:
                    if (x+y) % 2 == 0:  # black squares; it's this way round because my terminal window is black
                        out_string += '◦◦'
                    else:           # white squares
                        out_string += '••'
                out_string += ' '
            out_string += '| %s' % y
            out_string += '\n'
        out_string += """  +-------------------------+
    %s  """ % files
        if len(self.deadpieces) > 0:
            out_string += "\n"
            for p in self.deadpieces:
                out_string += "%s " % p.display()
        return out_string

    def __str__(self):
        return self.display(self.whose_turn)

    def show_moves(self, move_object):
        for piece_obj in move_object:
            if len(move_object[piece_obj]) > 0:
                print "%s@%s:" % (piece_obj, parse(piece_obj.pos)),
                for m in move_object[piece_obj]:
                    print parse(m),
                print ""

    def is_in_check(self, col):  # contra the name, this function is also where pins are detected
        log("Checking if %s is in check" % col)
        # checking_moves = self.gen_all_moves(opposite(col), attack_map = True)
        # though the pin detection code is actually in the gen_moves function
        check_number = 0
        for piece, pmoves in self.threatened_moves.iteritems():
            for move in pmoves:
                target = self.squares[move]
                if isinstance(target, King) and target.col == col:  # this might be a weird hack, but else you get self-checks??
                    check_number += 1
                    self.checking_piece = piece
        if check_number > 0:
            log("%s is in check" % col)
            self.playermessage("=============CHECK=============")
        return check_number

    def advance_turn(self):  # this is the refresh/update function
        self.whose_turn = opposite(self.whose_turn)
        log("Resetting list of pinned pieces")
        self.pinned_pieces = {}
        log("Setting list of %s's available moves" % self.whose_turn)
        self.threatened_moves, self.threatened_specials = self.gen_all_moves(opposite(self.whose_turn), attack_map=True)
        self.check = self.is_in_check(self.whose_turn)  # this function also sets the list of pinned pieces
        if self.check:  # intentionally not if == True, because check can be 2
            log("%s is in check, so pruning the movelist" % self.whose_turn)
            self.available_moves, self.available_specials = self.gen_checked_moves(self.whose_turn)
        else:
            self.available_moves, self.available_specials = self.gen_all_moves(self.whose_turn)  # generate moves for the new player
        for piece, vector in self.pinned_pieces.iteritems():  # prune moves for pinned pieces
                new_movelist = []
                for move in self.available_moves[piece]:
                    if move in vector:
                        new_movelist.append(move)
                self.available_moves[piece] = new_movelist
        if self.enpassant_clock is 2:
            self.enpassant_clock = 1
        else:
            self.enpassant_clock = 0
            self.enpassant = None
        # end of game detection:
        num_moves = 0
        for moves in self.available_moves.values():
            num_moves += len(moves)
        if num_moves == 0:
            if self.check:
                self.playermessage("=============MATE!=============")
                self.winner = opposite(self.whose_turn)
            else:
                self.playermessage("===========STALEMATE===========")
                self.winner = "nobody"
        log("... Finished setting that list")
        if self.whose_turn == 'white':
            self.turn += 1
        self.halfmove_history.append(self.halfmove_clock)  # necessary for rewind function
        self.halfmove_clock += 1
        if self.halfmove_clock > 50:
            self.playermessage("===========STALEMATE===========")
            self.winner = "nobody"
        self.playermessage(self.display(self.whose_turn))  # show the board
        log("Done advancing turn")

    def move(self, oldpos, newpos):  # board-centric move function
        piece_obj = self.squares[oldpos]
        try:
            specmoves = [n[0] for n in self.available_specials[piece_obj]]
        except Exception:
            specmoves = []
        # print "Checking for special moves"
        if newpos in specmoves:
            for speclist in self.available_specials[piece_obj]:
                if newpos == speclist[0]:
                    # print "Special move detected: %s" % speclist[1]
                    if speclist[1] == 'pawndouble':
                        piece_obj.double_move(newpos, self)
                    elif speclist[1] == 'enpassant':
                        piece_obj.en_passant(newpos, self)
                    elif speclist[1] == 'kside':
                        piece_obj.castle('kside', self)
                    elif speclist[1] == 'qside':
                        piece_obj.castle('qside', self)
                    elif speclist[1] == 'promotion':
                        piece_obj.promote(newpos, Queen, self)  # placeholder - queen only
                    break
                    # do special move
        else:
            self.squares[oldpos].move(newpos, self)  # just a wrapper for the piece-centric move

    def play(self, instring):  # this is a really ugly function but it's just for the user
        # takes standard chess notation as input, makes those moves from player side
        inlist = [c for c in instring if ((c != "x") and (c != "+") and (c != "#"))]   # strip x, + and # (they are unnecessary)
        instring = ''.join(inlist)
        done = False
        new_piece_class = None  # for promotion
        if "=" in instring:  # pawn promotion, we assume
            if instring[-1] == 'Q':
                new_piece_class = Queen
            elif instring[-1] == 'R':
                new_piece_class = Rook
            elif instring[-1] == 'N':
                new_piece_class = Knight
            elif instring[-1] == 'B':
                new_piece_class = Bishop
            instring = instring[0:-2]
        if instring == "O-O-O" or instring == "0-0-0":
            if self.whose_turn == 'white':
                self.pieces['w_king'].castle('qside', self)
                done = True
            else:
                self.pieces['b_king'].castle('qside', self)
                done = True
        elif instring == "O-O" or instring == "0-0":
            if self.whose_turn == 'white':
                self.pieces['w_king'].castle('kside', self)
                done = True
            else:
                self.pieces['b_king'].castle('kside', self)
                done = True
        elif len(instring) == 2:  # simple pawn move
            newsquare = parse(''.join(instring))
            for s in self.available_specials:
                if len(self.available_specials[s]) > 0:
                    if newsquare == self.available_specials[s][0][0] and self.available_specials[s][0][1] == 'pawndouble':
                        pawn_obj = s
                        pawn_obj.double_move(newsquare, self)
                        done = True
                        break
            if not done:
                if self.whose_turn == 'white':
                    movedir = array((0, 1))
                else:
                    movedir = array((0, -1))
                pawn_obj = self.squares[tuple(array(newsquare) - movedir)]
                if new_piece_class is not None:
                    pawn_obj.promote(newsquare, new_piece_class, self)
                else:
                    if newsquare[1] == 8 or newsquare[1] == 1:
                        self.playermessage("Please specify what piece to promote to")
                    else:
                        pawn_obj.move(newsquare, self)
                done = True
        elif len(instring) == 3:
            if instring[0] in ['N', 'K', 'R', 'Q', 'B']:  # move a non-pawn piece
                newsquare = parse(''.join(instring[1:3]))
                piece_symbols = {'N': Knight,
                                 'K': King,
                                 'R': Rook,
                                 'Q': Queen,
                                 'B': Bishop}
                # if instring[0] == 'N':
                #     piece_class = Knight
                # elif instring[0] == 'K':
                #     piece_class = King
                # elif instring[0] == 'R':
                #     piece_class = Rook
                # elif instring[0] == 'Q':
                #     piece_class = Queen
                # elif instring[0] == 'B':
                #     piece_class = Bishop
                piece_class = piece_symbols[instring[0]]
                move_count = 0
                for piece, moves in self.available_moves.iteritems():
                    if newsquare in moves and isinstance(piece, piece_class):
                        move_count += 1
                        right_piece = piece
                if move_count == 1:
                    right_piece.move(newsquare, self)
                    done = True
                elif move_count > 1:
                    self.playermessage("Ambiguous move, please clarify")
                    done = True
            elif instring[0] in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']:  # pawn capture
                newsquare = parse(''.join(instring[1:3]))
                done = False
                for s in self.available_specials:
                    if len(self.available_specials[s]) > 0:
                        if newsquare == self.available_specials[s][0][0] and self.available_specials[s][0][1] == 'enpassant':
                            pawn_obj = s
                            pawn_obj.en_passant(newsquare, self)
                            done = True
                            break
                if not done:
                    for piece, moves in self.available_moves.iteritems():
                        if newsquare in moves and isinstance(piece, Pawn):
                            if piece.pos[0] == ord(instring[0]) - 96:
                                if new_piece_class is not None:
                                    piece.promote(newsquare, new_piece_class, self)
                                else:
                                    if newsquare[1] == 8 or newsquare[1] == 1:
                                        self.playermessage("Please specify what piece to promote to")
                                    else:
                                        piece.move(newsquare, self)
                                done = True
                                break
        elif len(instring) == 4:  # ambiguous non-pawn move, we presume
            newsquare = parse(''.join(instring[2:4]))
            if instring[0] == 'N':
                piece_class = Knight
            elif instring[0] == 'K':
                piece_class = King
            elif instring[0] == 'R':
                piece_class = Rook
            elif instring[0] == 'Q':
                piece_class = Queen
            elif instring[0] == 'B':
                piece_class = Bishop
            if instring[1] in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']:
                piece_file = ord(instring[1]) - 96
            else:
                piece_rank = int(instring[1])
            move_count = 0
            for piece, moves in self.available_moves.iteritems():
                if newsquare in moves and isinstance(piece, piece_class):
                    if 'piece_file' in locals():
                        if piece.pos[0] == piece_file:
                            move_count += 1
                            right_piece = piece
                    else:
                        if piece.pos[1] == piece_rank:
                            move_count += 1
                            right_piece = piece
            if move_count == 1:
                right_piece.move(newsquare, self)
                done = True
            elif move_count > 1:
                self.playermessage("Extremely ambiguous move, please clarify exact squares (in the form Qg7h8)")
                done = True
        elif len(instring) == 5:
            oldsquare = parse(''.join(instring[1:3]))
            newsquare = parse(''.join(instring[3:5]))
            piece = self.squares[oldsquare]
            piece.move(newsquare, self)
            done = True
        if not done:
            self.playermessage("Illegal move, please try again.")

    def rewind(self):  # opposite of advance turn
        if self.whose_turn == 'white':
            self.turn -= 1
        self.whose_turn = opposite(self.whose_turn)
        lastmove = self.movehistory.pop()
        newpos = lastmove[0][1]
        oldpos = lastmove[0][0]
        movetype = lastmove[1]
        piece = self.squares[newpos]
        piece.pos = oldpos
        self.squares[newpos] = None
        self.squares[oldpos] = piece

        if 'capture' in movetype:
            cap_piece = self.deadpieces.pop()
            cap_piece.pos = newpos
            self.squares[newpos] = cap_piece
            self.pieces[cap_piece.display()+str(self.turn)] = cap_piece  # arbitrary piece name, shouldn't matter
        elif movetype == 'enpassant':
            if self.whose_turn == 'white':
                movedir = array((0, 1))
            else:
                movedir = array((0, -1))
            deadpos = tuple(array(newpos) - movedir)
            cap_piece = self.deadpieces.pop()
            cap_piece.pos = deadpos
            self.squares[deadpos] = cap_piece
            self.pieces[cap_piece.display()+str(self.turn)] = cap_piece
        elif movetype == 'kside':
            if self.whose_turn == 'white':
                rookpos = (8, 1)
                rookpiece = self.squares[(6, 1)]
            else:
                rookpos = (8, 8)
                rookpiece = self.squares[(6, 8)]
            rookpiece.pos = rookpos
            self.squares[rookpos] = rookpiece
        elif movetype == 'qside':
            if self.whose_turn == 'white':
                rookpos = (1, 1)
                rookpiece = self.squares[(4, 1)]
            else:
                rookpos = (1, 8)
                rookpiece = self.squares[(4, 8)]
            rookpiece.pos = rookpos
            self.squares[rookpos] = rookpiece
        if 'promo' in movetype:
            piece = Pawn(self.whose_turn, oldpos)

        self.halfmove_clock = self.halfmove_history.pop()

        # some duplicate code:

        self.pinned_pieces = {}
        log("Setting list of %s's available moves" % self.whose_turn)
        self.threatened_moves, self.threatened_specials = self.gen_all_moves(opposite(self.whose_turn), attack_map=True)
        self.check = self.is_in_check(self.whose_turn)  # this function also sets the list of pinned pieces
        if self.check:  # intentionally not if == True, because check can be 2
            log("%s is in check, so pruning the movelist" % self.whose_turn)
            self.available_moves, self.available_specials = self.gen_checked_moves(self.whose_turn)
        else:
            self.available_moves, self.available_specials = self.gen_all_moves(self.whose_turn)  # generate moves for the new player
        for piece, vector in self.pinned_pieces.iteritems():  # prune moves for pinned pieces
                new_movelist = []
                for move in self.available_moves[piece]:
                    if move in vector:
                        new_movelist.append(move)
                self.available_moves[piece] = new_movelist

    def encode(self):
        charlist = []
        for y in range(8, 0, -1):
            emptycount = 0
            if y != 8:
                charlist.append('/')
            for x in range(1, 9):
                if isinstance(self.squares[(x, y)], Piece):
                    if emptycount != 0:
                        charlist.append(str(emptycount))
                        emptycount = 0
                    charlist.append(self.squares[(x, y)].fensymbol)
                else:
                    emptycount += 1
            if emptycount != 0:
                charlist.append(str(emptycount))
            # charlist.append('/')

        charlist.append(' %s ' % self.whose_turn[0])

        castlecount = 0
        if not(self.pieces['w_king'].has_moved or self.pieces['w_k_rook'].has_moved):
            charlist.append('K')
            castlecount += 1
        if not(self.pieces['w_king'].has_moved or self.pieces['w_q_rook'].has_moved):
            charlist.append('Q')
            castlecount += 1
        if not(self.pieces['b_king'].has_moved or self.pieces['b_k_rook'].has_moved):
            charlist.append('k')
            castlecount += 1
        if not(self.pieces['b_king'].has_moved or self.pieces['b_q_rook'].has_moved):
            charlist.append('q')
            castlecount += 1
        if castlecount == 0:
            charlist.append('-')

        if self.enpassant is not None:
            charlist.append(' %s' % parse(self.enpassant))
        else:
            charlist.append(' -')
        charlist.append(' %s' % self.halfmove_clock)
        charlist.append(' %s' % self.turn)

        return ''.join(charlist)

    def playermessage(self, message):
        if self.real_game:
            # print message
            pass

    def __init__(self):
        self.newgame()


def log(message):
    if debug:
        print message


def decode(fenstring):
    b = Board()
    b.squares = {}
    b.pieces = {}
    fen_symbols = {'r': (Rook, 'black'),
                   'n': (Knight, 'black'),
                   'b': (Bishop, 'black'),
                   'k': (King, 'black'),
                   'q': (Queen, 'black'),
                   'p': (Pawn, 'black'),
                   'R': (Rook, 'white'),
                   'N': (Knight, 'white'),
                   'B': (Bishop, 'white'),
                   'K': (King, 'white'),
                   'Q': (Queen, 'white'),
                   'P': (Pawn, 'white')}
    squarenum = 0
    fenlist = fenstring.split(' ')
    for char in fenlist[0]:
        col = 8 - (squarenum // 8)
        row = (squarenum % 8) + 1
        if char.isdigit():
            for n in range(0, int(char)):
                col = 8 - (squarenum // 8)
                row = (squarenum % 8) + 1
                b.squares[(row, col)] = None
                squarenum += 1
        elif char == '/':
            pass
        else:
            lookup = fen_symbols[char]
            piece = lookup[0](lookup[1], (row, col))
            b.squares[(row, col)] = piece
            b.pieces['%s%s' % (char, squarenum)] = piece
            # check castling availability:
            if (char == 'r') and ((row, col) == (1, 8)) and ('q' in fenlist[2]):
                piece.has_moved = False
            else:
                piece.has_moved = True
            if (char == 'r') and ((row, col) == (8, 8)) and ('k' in fenlist[2]):
                piece.has_moved = False
            else:
                piece.has_moved = True
            if (char == 'R') and ((row, col) == (1, 1)) and ('Q' in fenlist[2]):
                piece.has_moved = False
            else:
                piece.has_moved = True
            if (char == 'R') and ((row, col) == (8, 1)) and ('K' in fenlist[2]):
                piece.has_moved = False
            else:
                piece.has_moved = True
            squarenum += 1

    if fenlist[1] == 'w':  # this is the opposite, so we can advance turn later
        b.whose_turn = 'black'
    else:
        b.whose_turn = 'white'

    if fenlist[3] != '-':
        b.enpassant = (row, col)
        b.enpassant_clock = 1
    else:
        b.enpassant = None
        b.enpassant_clock = 0

    b.halfmove_clock = int(fenlist[4]) - 1
    b.turn = int(fenlist[5]) - 1

    b.check = False
    b.checking_piece = None
    b.pinned_pieces = {}
    b.winner = None
    b.threatened_moves = {}
    b.deadpieces = []
    b.movehistory = []
    b.real_game = False

    b.advance_turn()

    return b

if __name__ == '__main__':
    while True:
        x = raw_input()
        gui_process(x)
