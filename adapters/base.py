from abc import ABC, abstractmethod

class SourceAdapter(ABC):
    name = "base"
    @abstractmethod
    def assets(self): return []
    @abstractmethod
    def sales(self): return []
    @abstractmethod
    def market_snapshots(self): return []
    @abstractmethod
    def population_snapshots(self): return []
    @abstractmethod
    def athlete_snapshots(self): return []
    @abstractmethod
    def hierarchy_comparables(self): return []
