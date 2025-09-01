from dataclasses import dataclass, field
from typing import Dict, Set

@dataclass
class ClientInfo:
    client_id: str
    online: bool = False
    announced: bool = False
    entities_published: bool = False
    topics: Set[str] = field(default_factory=set)
