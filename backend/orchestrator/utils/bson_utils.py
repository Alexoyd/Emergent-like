import dataclasses
from enum import Enum
from pathlib import Path
from datetime import datetime, date
import uuid
from decimal import Decimal

def bson_safe(obj):
    if isinstance(obj, Enum):
        return obj.value
    if dataclasses.is_dataclass(obj):
        obj = dataclasses.asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj  # OK pour PyMongo
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: bson_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [bson_safe(v) for v in obj]
    return obj
