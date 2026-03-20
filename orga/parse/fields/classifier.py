from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass, field
import math
import re
from orga.model import Document
from orga.registry import registry
from selectolax.parser import HTMLParser

@dataclass
class ClassificationResult:
    categories: List[str]
    debug_info: Dict[str, Any] = field(default_factory=dict)

class CategoryClassifierStrategy(ABC):
    """
    Abstract base class for all category classification strategies.
    """
    @abstractmethod
    def classify(self, doc: Document) -> ClassificationResult:
        pass

class RuleBasedClassifier(CategoryClassifierStrategy):
    """
    Tier 1: High-precision matching using structural signals (Title, H1, Meta, JSON-LD).
    """
    ZONE_WEIGHTS = {
        "title": 10.0,
        "h1": 5.0,
        "meta": 3.0,
        "jsonld": 15.0,
        "body": 1.0
    }

    def __init__(self, taxonomy: Dict[str, Any], weights: Dict[str, float] = None, threshold: float = 2.0):
        self.taxonomy = taxonomy
        self.zone_weights = weights or self.ZONE_WEIGHTS
        self.threshold = threshold

    def classify(self, doc: Document) -> ClassificationResult:
        if not doc.content:
            return ClassificationResult(categories=[])
            
        tree = HTMLParser(doc.content)
        scores = {}
        debug_scores = {}
        
        zones = {
            "title": (tree.css_first("title").text(strip=True).lower() if tree.css_first("title") else ""),
            "h1": " ".join([n.text(strip=True).lower() for n in tree.css("h1")]),
            "meta": self._get_meta_text(tree),
            "body": (tree.body.text(separator=" ") or "").lower() if tree.body else ""
        }
        
        for cat, config in self.taxonomy.items():
            if isinstance(config, list):
                rules = {"title": config, "h1": config, "meta": config, "body": config}
                negatives = []
            elif isinstance(config, dict):
                negatives = config.get("negative_keywords", [])
                rules = config.get("rules", {})
                if not rules and "keywords" in config:
                    kws = config["keywords"]
                    rules = {"title": kws, "h1": kws, "meta": kws, "body": kws}
            else:
                continue

            # zones["body"] is now guaranteed to be string (empty string at worst)
            if any(n.lower() in zones["body"] for n in negatives):
                debug_scores[cat] = {"score": 0.0, "reason": "negative_keyword"}
                continue

            cat_score = 0.0
            for zone, keywords in rules.items():
                weight = self.zone_weights.get(zone, 1.0)
                zone_text = zones.get(zone, "")
                
                if isinstance(keywords, dict):
                    for kw, kw_w in keywords.items():
                        if kw.lower() in zone_text:
                            cat_score += weight * kw_w
                else:
                    for kw in keywords:
                        if kw.lower() in zone_text:
                            cat_score += weight
            
            if cat_score > 0:
                scores[cat] = cat_score
                debug_scores[cat] = {"score": round(cat_score, 2), "source": "rule_based"}
                
        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        # Use configurable threshold
        categories = [c[0] for c in sorted_cats if c[1] >= self.threshold]
        
        return ClassificationResult(
            categories=categories,
            debug_info={
                "candidates": debug_scores,
                "threshold": self.threshold,
                "top_scores": sorted_cats[:3]
            }
        )

    def _get_meta_text(self, tree: HTMLParser) -> str:
        texts = []
        for name in ["description", "keywords"]:
            node = tree.css_first(f"meta[name='{name}']")
            if node:
                # content attribute might be None if value is missing <meta content>
                content_val = node.attributes.get("content")
                texts.append((content_val or "").lower())
        return " ".join(texts)

class BayesianClassifier(CategoryClassifierStrategy):
    """
    Tier 2: Statistical frequency-based classification using body tokens.
    """
    THRESHOLD = 0.0 

    def __init__(self, taxonomy: Dict[str, Any]):
        self.taxonomy = taxonomy

    def classify(self, doc: Document) -> ClassificationResult:
        if not doc.content:
            return ClassificationResult(categories=[])
            
        tree = HTMLParser(doc.content)
        body_text = (tree.body.text(separator=" ") or "").lower() if tree.body else ""
        
        scores = {}
        debug_scores = {}
        
        for cat, config in self.taxonomy.items():
            if isinstance(config, list):
                features = config
                negatives = []
            elif isinstance(config, dict):
                negatives = config.get("negative_keywords", [])
                features = config.get("bayes_features", {})
                if not features and "keywords" in config:
                    features = config["keywords"]
            else:
                continue

            if any(n.lower() in body_text for n in negatives):
                debug_scores[cat] = {"score": 0.0, "reason": "negative_keyword"}
                continue

            cat_score = 0.0
            if isinstance(features, dict):
                for word, weight in features.items():
                    count = body_text.count(word.lower())
                    if count > 0:
                        cat_score += weight * math.log1p(count)
            elif isinstance(features, (list, set)):
                for word in features:
                    count = body_text.count(word.lower())
                    if count > 0:
                        cat_score += 1.0 * math.log1p(count)
            
            if cat_score > 0:
                scores[cat] = cat_score
                debug_scores[cat] = {"score": round(cat_score, 2), "source": "bayesian"}
                
        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        categories = [c[0] for c in sorted_cats if c[1] > self.THRESHOLD]
        
        return ClassificationResult(
            categories=categories,
            debug_info={
                "candidates": debug_scores,
                "threshold": self.THRESHOLD,
                "top_scores": sorted_cats[:3]
            }
        )

class LayeredCategoryClassifier(CategoryClassifierStrategy):
    """
    The Orchestrator for the Classification Subsystem (Section 11).
    Implements Tier 1 -> Tier 2 flow with Margin Checks.
    """
    def __init__(self, 
                 taxonomy: Dict[str, Any], 
                 weights: Dict[str, float] = None, 
                 thresholds: Dict[str, float] = None):
        
        self.taxonomy = taxonomy
        self.weights = weights
        
        # Default thresholds (fallback)
        self.config = thresholds or {}
        self.tier1_min = self.config.get("tier1_threshold", 2.0)
        self.tier2_min = self.config.get("tier2_min_score", 0.5)
        self.margin = self.config.get("tier2_margin", 0.1)
        self.top_k = int(self.config.get("top_k", 1))
        
        # Initialize Tiers
        self.tier1 = RuleBasedClassifier(self.taxonomy, weights=weights, threshold=self.tier1_min)
        self.tier2 = BayesianClassifier(self.taxonomy)

    def classify(self, doc: Document) -> ClassificationResult:
        # 1. Tier 1 (Strong Rules)
        t1_result = self.tier1.classify(doc)
        
        debug_info = {
            "tier1_debug": t1_result.debug_info,
            "tier2_debug": {},
            "decision_path": [],
            "final_candidates": {},
            "threshold_config": {
                "tier1_threshold": self.tier1_min,
                "tier2_min_score": self.tier2_min,
                "margin": self.margin,
                "top_k": self.top_k
            }
        }
        
        if t1_result.categories:
            debug_info["decision_path"].append("Tier 1 (Rules) match found.")
            debug_info["final_candidates"] = t1_result.debug_info.get("candidates", {})
            return ClassificationResult(
                categories=t1_result.categories[:self.top_k],
                debug_info=debug_info
            )
            
        debug_info["decision_path"].append("Tier 1 yielded no high-confidence results. Falling back to Tier 2 (Bayesian).")
        
        # 2. Tier 2 (Weak / Statistical)
        t2_result = self.tier2.classify(doc)
        debug_info["tier2_debug"] = t2_result.debug_info
        
        top_scores = t2_result.debug_info.get("top_scores", [])
        
        if not top_scores:
            debug_info["decision_path"].append("Tier 2 yielded no results (score=0).")
            return ClassificationResult(categories=[], debug_info=debug_info)

        # Margin Check Logic
        top1_cat, top1_score = top_scores[0]
        top2_cat, top2_score = top_scores[1] if len(top_scores) > 1 else (None, 0.0)
        
        # 1. Min Score Check
        if top1_score < self.tier2_min:
            debug_info["decision_path"].append(f"Tier 2 Top-1 score ({top1_score}) is below min_score ({self.tier2_min}). Rejected.")
            return ClassificationResult(categories=[], debug_info=debug_info)
            
        # 2. Margin Check
        gap = top1_score - top2_score
        if gap < self.margin:
             debug_info["decision_path"].append(f"Tier 2 Ambiguous result. Gap ({gap:.2f}) < Margin ({self.margin}). Rejected.")
             return ClassificationResult(categories=[], debug_info=debug_info)
             
        # Success
        debug_info["decision_path"].append(f"Tier 2 match found via Margin check (Gap={gap:.2f}).")
        debug_info["final_candidates"] = t2_result.debug_info.get("candidates", {})
        
        return ClassificationResult(
            categories=[top1_cat], # Conservative Top-1
            debug_info=debug_info
        )

class WeightedHeuristicClassifier(LayeredCategoryClassifier):
    def __init__(self, 
                 taxonomy: Dict[str, Any] = None, 
                 weights: Dict[str, float] = None, 
                 config: Dict[str, Any] = None,
                 min_score: float = None, # Backwards compat
                 margin: float = None     # Backwards compat
                 ):
        tax = taxonomy or config or {}
        
        # Construct thresholds dict from old args if present
        thresholds = {}
        if min_score is not None:
            thresholds["tier2_min_score"] = min_score
        if margin is not None:
            thresholds["tier2_margin"] = margin
            
        super().__init__(taxonomy=tax, weights=weights, thresholds=thresholds)

class CategoryClassifier(WeightedHeuristicClassifier):
    pass

registry.register("category_classifier", "weighted_heuristic", LayeredCategoryClassifier)
registry.register("category_classifier", "layered", LayeredCategoryClassifier)
registry.register("category_classifier", "rule_based", RuleBasedClassifier)
registry.register("category_classifier", "bayesian", BayesianClassifier)
