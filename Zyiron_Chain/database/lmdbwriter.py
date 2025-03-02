
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))




class LMDBAtomicWriter:
    def __init__(self, db):
        self.db = db
        self.txn = None
        
    def __enter__(self):
        self.txn = self.db.env.begin(write=True)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.txn.commit()
        else:
            self.txn.abort()
        self.txn = None



class StorageInitError(Exception):
    """Critical storage initialization failure"""
    pass

class CorruptedBlockFileError(Exception):
    """Block data file corruption detected"""
    pass
