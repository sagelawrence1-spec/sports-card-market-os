from dataclasses import dataclass, field
from typing import Dict, Any, List

@dataclass
class Asset:
    card_id: str
    raw: Dict[str, Any]

@dataclass
class DerivedFeatures:
    card_id: str
    observation_id: str
    player: str
    sport: str
    values: Dict[str, float]
    context: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Signal:
    observation_id: str
    card_id: str
    player: str
    sport: str
    signal: str
    confidence: float
    ir_score: float
    rar_score: float
    mi_score: float
    cie_score: float
    alerts: List[str]
    thesis: str
    diagnostics: Dict[str, float]
