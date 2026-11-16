from .chessbase_cbh_reader import ChessBaseReader
from .format_detector import entrypoint,family
from .reader_interface import Capabilities
from .standard_readers import PgnReader,PolyglotReader,PositionReader
READERS={'.cbh':ChessBaseReader,'.2cbh':ChessBaseReader,'.pgn':PgnReader,'.gz':PgnReader,'.bin':PolyglotReader,'.fen':PositionReader,'.epd':PositionReader}
def open_reader(path):
    p=entrypoint(path)
    if p is None:raise ValueError('Select the database entry point; required companion is missing')
    if p.suffix.lower() not in READERS:raise ValueError('No verified native adapter for '+p.suffix)
    return READERS[p.suffix.lower()](p)
