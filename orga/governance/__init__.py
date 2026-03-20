from typing import List, Dict, Any, Optional
from orga.model import (
    OrganizationProfile, Evidence, Warning, 
    WarningSeverity, Confidence, Location, ContactKind
)

# Default Weights and Reliabilities for Evidence Types
# Defined in Design Doc 12.2
SOURCE_TYPE_METRICS = {
    "jsonld_address": {"weight": 1.0, "reliability": 1.0},
    "jsonld_org_name": {"weight": 1.0, "reliability": 1.0},
    "html_attr_tel": {"weight": 0.9, "reliability": 0.95},
    "html_attr_mailto": {"weight": 0.9, "reliability": 0.95},
    "html_attr_social": {"weight": 0.8, "reliability": 0.9},
    "regex_text_validated": {"weight": 0.5, "reliability": 0.7},
    "parsed_address": {"weight": 0.7, "reliability": 0.8},
    "heuristic_text": {"weight": 0.3, "reliability": 0.5},
    "text_matcher_validated": {"weight": 0.6, "reliability": 0.7},
}

class ScoringEngine:
    """
    Implements mathematical scoring formulas from Design Document Section 12.3.
    """

    def calculate_field_score(self, evidences: List[Evidence]) -> float:
        """
        Calculate field-level score using weighted average formula:
        score = sum(w_i * r_i) / sum(w_i)
        """
        if not evidences:
            return 0.0
        
        total_weighted_reliability = 0.0
        total_weight = 0.0
        
        for ev in evidences:
            metrics = SOURCE_TYPE_METRICS.get(ev.source_type, {"weight": 0.5, "reliability": 0.5})
            w = metrics["weight"]
            r = ev.confidence_score if ev.confidence_score > 0 else metrics["reliability"]
            
            total_weighted_reliability += w * r
            total_weight += w
            
        return round(total_weighted_reliability / total_weight, 2) if total_weight > 0 else 0.0

    def calculate_profile_score(self, profile: OrganizationProfile) -> float:
        """
        Calculate profile-level score with completeness penalty:
        score_profile = (sum(alpha_f * score_f)) * beta_completeness
        """
        # alpha_f: relative importance of fields
        weights = {
            "name": 0.3,
            "locations": 0.4,
            "contacts": 0.3 # phones + emails + socials
        }
        
        sum_weighted_scores = 0.0
        
        # 1. Name score
        if profile.name:
            sum_weighted_scores += weights["name"] * 1.0
            
        # 2. Locations score
        if profile.locations:
            loc_scores = [loc.confidence for loc in profile.locations]
            avg_loc_score = max(loc_scores) if loc_scores else 0.0 # Use max for profile strength
            sum_weighted_scores += weights["locations"] * avg_loc_score
            
        # 3. Contacts score
        all_contacts = profile.phones + profile.emails + profile.social_links
        if all_contacts:
            contact_scores = [c.confidence for c in all_contacts]
            avg_contact_score = max(contact_scores) if contact_scores else 0.0
            sum_weighted_scores += weights["contacts"] * avg_contact_score
            
        # beta_completeness: Penalty for missing critical fields (Design Doc 12.3.2)
        beta = 1.0
        if not profile.locations:
            beta *= 0.7
        if not profile.phones and not profile.emails:
            beta *= 0.8
        if not profile.categories:
            beta *= 0.9
            
        return round(sum_weighted_scores * beta, 2)

class WarningRegistry:
    """
    Standardized Warning Codes implementation (Design Doc 12.4.1).
    """

    def scan_for_warnings(self, profile: OrganizationProfile) -> List[Warning]:
        """
        Scan a profile and generate standardized warnings according to the contract.
        """
        warnings = []
        
        # EMPTY_PROFILE
        if not profile.name and not profile.locations and not profile.phones and not profile.emails:
            warnings.append(Warning(
                code="EMPTY_PROFILE",
                message="No significant profile data extracted",
                severity=WarningSeverity.ERROR
            ))
            return warnings

        # NO_LOCATION_FOUND
        if not profile.locations:
            warnings.append(Warning(
                code="NO_LOCATION_FOUND",
                message="No physical address found in documentation",
                severity=WarningSeverity.WARNING
            ))
        else:
            # ADDRESS_PARTIALLY_PARSED
            for loc in profile.locations:
                if loc.address.raw and not (loc.address.street or loc.address.city):
                    warnings.append(Warning(
                        code="ADDRESS_PARTIALLY_PARSED",
                        message="Address found but only raw string was extracted",
                        severity=WarningSeverity.WARNING,
                        related_field="locations"
                    ))
                    break

        # NO_CONTACT_FOUND
        if not profile.phones and not profile.emails and not profile.social_links:
            warnings.append(Warning(
                code="NO_CONTACT_FOUND",
                message="No telephone, email or social media links found",
                severity=WarningSeverity.WARNING
            ))

        # CLASSIFICATION_LOW_CONFIDENCE (Aligned with Design Doc 12.4.1)
        if not profile.categories:
            warnings.append(Warning(
                code="CLASSIFICATION_LOW_CONFIDENCE",
                message="Business classification confidence is low or no categories found",
                severity=WarningSeverity.WARNING
            ))

        # LOW_CONFIDENCE_FIELD
        if profile.confidence and profile.confidence.overall_score < 0.4:
             warnings.append(Warning(
                code="LOW_CONFIDENCE_FIELD",
                message=f"Overall profile confidence is low ({profile.confidence.overall_score})",
                severity=WarningSeverity.WARNING
            ))

        return warnings
