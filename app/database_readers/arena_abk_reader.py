"""Read-only ABK node walk adapted from ChessX arenabook.cpp/abk.h (GPL-2.0-or-later).
Copyright ChessX ABK reference: Jens Nissen, 2017. Python adaptation CBA, 2026.
Real-world compatibility remains PARTIAL SUPPORT until representative books are tested.
"""
import mmap,struct
from pathlib import Path
import chess
class ArenaBookReader:
    def __init__(self,path):self.path=Path(path)
    def entries(self,cancel=lambda:False):
        size=self.path.stat().st_size
        if size<901*28 or size%28:raise ValueError('Invalid ABK record layout (28-byte records; root node 900)')
        with self.path.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            stack=[(900,chess.Board(),frozenset())]
            while stack:
                if cancel():raise InterruptedError('ABK import cancelled')
                index,board,parents=stack.pop()
                if index in parents or len(parents)>512:raise ValueError('ABK cycle or excessive depth')
                if index<900 or index*28+28>size:raise ValueError('ABK node pointer outside file')
                a,b,promo,priority,games,won,lost,hz,child,sibling=struct.unpack_from('<BBBBIIIIii',data,index*28)
                promotion={0:None,1:chess.ROOK,2:chess.KNIGHT,3:chess.BISHOP,4:chess.QUEEN}.get(promo)
                move=chess.Move(a,b,promotion=promotion)
                if move not in board.legal_moves:raise ValueError(f'Illegal ABK move at record {index}')
                yield dict(board=board,move=move,weight=games or priority or 1)
                if sibling>0:stack.append((sibling,board.copy(),parents|{index}))
                if child>0:
                    after=board.copy();after.push(move);stack.append((child,after,parents|{index}))
