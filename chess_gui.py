#!/usr/bin/env python
# -*- coding: utf-8 -*-

import wx
import json
import subprocess
import threading
import sys


def square_to_coord(square):
    bottom_corner = (480, 0)
    unit = 60
    squarex = square[0]
    squarey = square[1]-1
    newx = (squarex*unit) - 60
    newy = bottom_corner[0] - (unit + squarey*unit)
    return(newx, newy)


def coord_to_square(coord):
    x = coord[0]
    y = coord[1]
    squarex = 1 + int(x/60)
    squarey = 8 - int(y/60)
    return (squarex, squarey)


def square_to_string(square):
    x = str(square[0])
    y = str(square[1])
    return x+y


def string_to_square(string):
    return (int(string[0]), int(string[1]))


class ChessBoard(wx.Frame):
    def __init__(self, parent, title):
        self.engine = subprocess.Popen('./chess_engine.py',
                                       stdout=subprocess.PIPE, stdin=subprocess.PIPE,
                                       bufsize=0, universal_newlines=True)
        self.engine.stdin.write('{"command": "newGame"}\n')
        self.engine.stdin.flush()
        self.activepiece = None
        self.winner = None

        self.filenames = {'wp': 'png/Chess_wpawn.png',
                          'bp': 'png/Chess_bpawn.png',
                          'wK': 'png/Chess_wking.png',
                          'bK': 'png/Chess_bking.png',
                          'wQ': 'png/Chess_wqueen.png',
                          'bQ': 'png/Chess_bqueen.png',
                          'wB': 'png/Chess_wbishop.png',
                          'bB': 'png/Chess_bbishop.png',
                          'wN': 'png/Chess_wknight.png',
                          'bN': 'png/Chess_bknight.png',
                          'wR': 'png/Chess_wrook.png',
                          'bR': 'png/Chess_brook.png'}

        thread = threading.Thread(target=self.run)
        thread.setDaemon(True)
        thread.start()

        wx.Frame.__init__(self, parent, title=title, size=(480, 480))
        #self.CreateStatusBar()

        self.chess_panel = wx.Panel(self)

        # menu:
        filemenu = wx.Menu()

        menuNewGame = filemenu.Append(wx.ID_ANY, "&New Game", "Clear the board and start again")
        menuAbout = filemenu.Append(wx.ID_ABOUT, "&About", "Information about this program")
        menuExit = filemenu.Append(wx.ID_EXIT, "E&xit", "Terminate the program")

        menuBar = wx.MenuBar()
        menuBar.Append(filemenu, "&File")
        self.SetMenuBar(menuBar)

        self.Bind(wx.EVT_MENU, self.OnAbout, menuAbout)
        self.Bind(wx.EVT_MENU, self.OnExit, menuExit)
        self.Bind(wx.EVT_MENU, self.OnNewGame, menuNewGame)

        self.chess_panel.Bind(wx.EVT_LEFT_DOWN, self.SquareClick)
        self.chess_panel.Bind(wx.EVT_RIGHT_DOWN, self.SquareRightClick)

        self.Centre()

        self.Show(True)

    def run(self):
        while True:
            x = self.engine.stdout.readline()
            print x
            wx.CallAfter(self.process_engine, x)

    def process_engine(self, jsonstring):
        print "received json message from engine: " + jsonstring
        try:
            jsondict = json.loads(jsonstring)
        except Exception as x:
            print "error: %s" % x
            sys.exit()
        message = jsondict[u'message']
        if message == 'boardState':
            self.boardstate = jsondict['board']
            if jsondict['winner'] == 'None':
                self.whose_turn = jsondict['turn']
                self.DrawBoard(self.boardstate)
            else:
                self.DrawBoard(self.boardstate)
                self.winner = jsondict['winner']
                print "The winner is %s" % self.winner.capitalize()
#               dlg = wx.MessageDialog(self, "%s wins" % self.winner.capitalize())
#               dlg.ShowModal()
#               dlg.Destroy()
        elif message == 'pieceMoves':
            piece_pos = jsondict['piecePos']
            movelist = jsondict['moves']
            squares_to_highlight = [string_to_square(piece_pos)]
            for square in movelist:
                squares_to_highlight.append(string_to_square(square))

            self.HighlightSquares(squares_to_highlight)
            # self.HighlightMoves ?
        elif message == 'gameOver':
            self.winner = jsondict['winner']
            print "%s wins" % self.winner.capitalize()

    def HighlightSquares(self, squares):
        self.DrawBoard(self.boardstate)
        for square in squares:
            dc = wx.PaintDC(self.chess_panel)
            dc.SetPen(wx.Pen('#000000'))
            r, c = square[0]-1, 8-square[1]
            dc.SetBrush(wx.Brush('gold'))
#           if (square[0] + square[1]) % 2 == 0:
#               dc.SetBrush(wx.Brush('gold'))
#           else:
#               dc.SetBrush(wx.Brush('gold'))
            dc.DrawRectangle(r*60, c*60, 60, 60)

            piece = self.boardstate[str(square[0])+str(square[1])]
            self.DrawPiece(square, piece)

    def SquareClick(self, e):
        if self.winner is None:
            print "Click detected at %s" % e.GetPosition()
            clickpos = e.GetPosition()
            clicksquare = coord_to_square(clickpos)
            active_turn = self.whose_turn[0]
            piece = self.boardstate[square_to_string(clicksquare)]
            if piece != 'None' and piece[0] == active_turn:
                self.activepiece = clicksquare
                jsonstring = '{"command": "getMoves", "piecePos": "%s"}\n' % square_to_string(clicksquare)
                self.engine.stdin.write(jsonstring)
            elif self.activepiece is not None:
                jsonstring = '{"command": "sendMove", "piecePos": "%s", "newPos": "%s"}\n' % \
                             (square_to_string(self.activepiece), square_to_string(clicksquare))
                print jsonstring
                self.activepiece = None
                self.DrawBoard(self.boardstate)
                self.engine.stdin.write(jsonstring)
        else:
            print "Click detected at %s, but the game is over" % e.GetPosition()

    def SquareRightClick(self, e):
        print "Click detected at %s" % e.GetPosition()
        clickpos = e.GetPosition()
        clicksquare = coord_to_square(clickpos)
        self.SetStatusText(str(clicksquare))
        piece = self.boardstate[square_to_string(clicksquare)]
        if piece != 'None':
            self.activepiece = clicksquare
            jsonstring = '{"command": "getStats", "piecePos": "%s"}\n' % square_to_string(clicksquare)
            # self.engine.stdin.write(jsonstring)
        elif self.activepiece is not None:
            jsonstring = '{"command": "sendMove", "piecePos": "%s", "newPos": "%s"}\n' % \
                         (square_to_string(self.activepiece), square_to_string(clicksquare))
            print jsonstring
            self.activepiece = None
            self.DrawBoard(self.boardstate)
            self.engine.stdin.write(jsonstring)

    def DrawPiece(self, pos, piece):
        if piece != 'None':
            coord = square_to_coord(pos)
            png = wx.Image(self.filenames[piece], wx.BITMAP_TYPE_ANY).ConvertToBitmap()
            dc = wx.PaintDC(self.chess_panel)
            dc.DrawBitmap(png, coord[0], coord[1], True)

    def DrawBoard(self, boardstate):
        dc = wx.PaintDC(self.chess_panel)
        dc.SetPen(wx.Pen('#000000'))
        for r in range(0, 8):
            for c in range(0, 8):
                if ((r+1)+(c+1)) % 2 == 0:
                    dc.SetBrush(wx.Brush('tan'))
                else:
                    dc.SetBrush(wx.Brush('sienna'))
                dc.DrawRectangle(r*60, c*60, 60, 60)
        for x, y in boardstate:
            piece = boardstate[x+y]
            if piece != 'None':
                pos = (int(x), int(y))
                self.DrawPiece(pos, piece)

    # non game methods:

    def OnAbout(self, e):
        dlg = wx.MessageDialog(self, "chess ai, routinely loses")
        dlg.ShowModal()
        dlg.Destroy()

    def OnExit(self, e):
        self.Close(True)

    def OnNewGame(self, e):
        self.engine.stdin.write('{"command": "newGame"}\n')


if __name__ == '__main__':
    app = None
    app = wx.App(False)

    frame = ChessBoard(None, 'chess_gui')
    print dir(frame)
    app.MainLoop()
