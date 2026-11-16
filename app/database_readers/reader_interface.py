"""Reader contracts: capabilities are explicit; opening alone never proves decoding."""
from dataclasses import dataclass,field
from typing import Protocol,Iterator
@dataclass
class Capabilities:
    random_access:bool=False
    annotations:bool=False
    native_headers:bool=False
    position_index:bool=False
    read_only:bool=True
@dataclass
class DatabaseInfo:
    format:str
    backend:str
    status:str
    records:int=0
    games:int=0
    size:int=0
    found:list=field(default_factory=list)
    missing:list=field(default_factory=list)
    detail:str=''
class Reader(Protocol):
    capabilities:Capabilities
    def metadata(self)->DatabaseInfo:...
    def game(self,identifier:int):...
    def enumerate(self,first:int=1,count:int=100)->Iterator[dict]:...
    def close(self):...
