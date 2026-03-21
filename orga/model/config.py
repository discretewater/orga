from typing import Any

from pydantic import BaseModel, Field

from orga.parse.taxonomy import DEFAULT_TAXONOMY


class ZoneWeightConfig(BaseModel):
    """
    Weights for different DOM zones.
    Used by classifiers and scoring models.
    """
    title: float = 10.0
    meta_desc: float = 5.0
    meta_keywords: float = 5.0
    h1: float = 3.0
    h2: float = 2.0
    nav: float = 2.0
    body: float = 1.0

class ClassificationThresholds(BaseModel):
    """
    Thresholds for the layered classification logic.
    """
    tier1_threshold: float = 2.0  # High confidence rule match
    tier2_min_score: float = 0.5  # Minimum score for statistical match
    tier2_margin: float = 0.1     # Required gap between Top-1 and Top-2
    top_k: int = 1                # Conservative output limit

class FetchConfig(BaseModel):
    timeout: int = 30
    retries: int = 2
    user_agent: str = "Mozilla/5.0 (Compatible; OrgaBot/0.1)"
    concurrency: int = 5
    per_host_concurrency: int = 2
    respect_robots: bool = True

class DiscoveryConfig(BaseModel):
    max_discovered_pages: int = 5
    strategy: str = "heuristic"

class ParseConfig(BaseModel):
    strategies: list[str] = ["json_ld", "meta_tags", "regex", "heuristic"]
    category_strategy: str = "weighted_heuristic"
    classification_thresholds: ClassificationThresholds = Field(default_factory=ClassificationThresholds)
    
class MergeConfig(BaseModel):
    strategy: str = "standard"

class GovernanceConfig(BaseModel):
    low_confidence_threshold: float = 0.5

class OrgaConfig(BaseModel):
    """
    ORGA Global Configuration.
    """
    fetch: FetchConfig = Field(default_factory=FetchConfig)
    discover: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    parse: ParseConfig = Field(default_factory=ParseConfig)
    merge: MergeConfig = Field(default_factory=MergeConfig)
    governance: GovernanceConfig = Field(default_factory=GovernanceConfig)
    
    # Shared weights
    weights: ZoneWeightConfig = Field(default_factory=ZoneWeightConfig)
    
    taxonomy: dict[str, Any] = Field(default_factory=lambda: DEFAULT_TAXONOMY, description="Weighted taxonomy definitions")
    
    def __init__(self, **data: Any):
        super().__init__(**data)
