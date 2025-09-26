import json, dataclasses
from enum import Enum
from pathlib import Path

def json_default(o):
    if isinstance(o, Enum):
        return o.value
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)

def dumps(obj, **kwargs):
    # évite "multiple values for argument 'default'"
    kwargs.setdefault("default", json_default)
    return json.dumps(obj, **kwargs)

def dump(obj, fp, **kwargs):
    kwargs.setdefault("default", json_default)
    return json.dump(obj, fp, **kwargs)
