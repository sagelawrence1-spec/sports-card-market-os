from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

@dataclass
class EvidenceRecord:
    provider: str
    record_type: str  # sold | active_listing
    source_item_id: str
    title: str
    price: float
    event_date: Optional[str] = None
    url: Optional[str] = None
    currency: str = "USD"
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProviderResult:
    records: List[EvidenceRecord]
    query: str
    provider: str
    metadata: Dict[str, Any] = field(default_factory=dict)

class SoldDataProvider(Protocol):
    def search_sold(self, query: str, **kwargs) -> ProviderResult: ...

class ListingProvider(Protocol):
    def search_active(self, query: str, **kwargs) -> ProviderResult: ...
