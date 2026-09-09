from dataclasses import dataclass
from pathlib import Path
import hashlib

@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    size: int
    mtime_ns: int
    content_hash: str

    def to_data(self):
        return {
            "size": self.size,
            "mtime_ns": self.mtime_ns,
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_data(cls, data):
        expected={"size","mtime_ns","content_hash"}
        if set(data)!=expected:
            raise ValueError("invalid fingerprint record")
        return cls(int(data["size"]), int(data["mtime_ns"]), str(data["content_hash"]))

def hash_file(path, *, chunk_size=1024*1024):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk=f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def fingerprint_file(path):
    p=Path(path)
    st=p.stat()
    return SourceFingerprint(
        size=st.st_size,
        mtime_ns=st.st_mtime_ns,
        content_hash=hash_file(p),
    )

def fast_unchanged(path, previous):
    p=Path(path)
    st=p.stat()
    return st.st_size==previous.size and st.st_mtime_ns==previous.mtime_ns
