import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from typing import Any, TypeVar
from urllib.parse import urlparse, urlunparse

from orga.governance import ScoringEngine, WarningRegistry
from orga.merge.constants import (
    ADDRESS_ABBREVIATIONS,
    GENERIC_SHARING_QUERY_KEYS,
    PHONE_MAX_REPETITION_RATIO,
    PHONE_MIN_DIGITS,
    SOCIAL_PLATFORMS,
)
from orga.model import (
    Address,
    Confidence,
    Contact,
    Evidence,
    Location,
    OrganizationProfile,
)
from orga.registry import registry

T = TypeVar('T')

class MergerStrategy(ABC):
    @abstractmethod
    def process(self, profile: OrganizationProfile) -> OrganizationProfile:
        pass

class ProfilePostProcessor(MergerStrategy):
    """
    Standard implementation of the Post-Processing Pipeline.
    Responsible for normalization, filtering, deduplication, and governance.
    Strictly separates Accepted and Internal evidence.
    Populates debug_info with filtered/rejected items.
    """

    def __init__(self):
        self.scoring_engine = ScoringEngine()
        self.warning_registry = WarningRegistry()

    def process(self, profile: OrganizationProfile) -> OrganizationProfile:
        """
        Executes the formal Post-Processing Pipeline sequence (Design Doc 7.6).
        """
        # Initialize debug info container
        if profile.debug_info is None:
            profile.debug_info = {}
        
        # 1. Normalization & Validation/Filtering & 2. Deduplication
        profile.emails, rejected_emails = self._process_contacts(profile.emails, self._normalize_email, lambda x: True)
        profile.phones, rejected_phones = self._process_contacts(profile.phones, self._normalize_phone, self._is_phone_plausible)
        profile.social_links, filtered_socials = self._process_contacts(profile.social_links, self._normalize_social, self._is_social_plausible)
        
        # Collect debug info
        if rejected_emails:
            profile.debug_info["rejected_emails"] = rejected_emails
        if rejected_phones:
            profile.debug_info["rejected_phones"] = rejected_phones
        if filtered_socials:
            profile.debug_info["filtered_social_links"] = filtered_socials

        # 3. Deduplication & Merging (Locations)
        profile.locations = self._process_locations(profile.locations)
        
        # 3.1 Final Output Sanitization (M6.1 Gatekeeper)
        profile.locations = self._sanitize_final_locations(profile.locations)
        
        # 4. Global Evidence Cleanup & Scoring (Physical Isolation of Evidence)
        self._refresh_governance(profile)
        
        # 5. Emit Final Warnings (Aligned with Standard Codes)
        profile.warnings = self.warning_registry.scan_for_warnings(profile)
        
        return profile

    def _process_contacts(
        self, 
        contacts: list[Contact], 
        normalizer: Callable[[str], str],
        validator: Callable[[str], bool]
    ) -> tuple[list[Contact], list[dict[str, Any]]]:
        merged: dict[str, Contact] = {}
        rejected = []
        
        for c in contacts:
            norm_val = normalizer(c.value)
            
            if not validator(norm_val):
                rejected.append({
                    "value": c.value, 
                    "normalized": norm_val, 
                    "reason": "validation_failed"
                })
                continue
            
            key = (c.kind, norm_val)
            if key not in merged:
                merged[key] = Contact(
                    kind=c.kind,
                    value=norm_val,
                    label=c.label,
                    evidence=[],
                    internal_evidence=[]
                )
            
            merged[key].evidence.extend(c.evidence)
            merged[key].internal_evidence.extend(c.internal_evidence)
            if not merged[key].label and c.label:
                merged[key].label = c.label
        
        results = []
        for c in merged.values():
            c.confidence = self.scoring_engine.calculate_field_score(c.evidence)
            if c.confidence >= 0.1:
                results.append(c)
            else:
                rejected.append({
                    "value": c.value,
                    "confidence": c.confidence,
                    "reason": "low_confidence"
                })
            
        return results, rejected

    def _process_locations(self, locations: list[Location]) -> list[Location]:
        """
        Deduplicates locations based on Fingerprint (Postal+StreetNumber) or Normalized Raw.
        """
        merged: dict[str, Location] = {}
        
        for loc in locations:
            # 1. Normalize raw address
            norm_raw = self._normalize_address(loc.address.raw)
            loc.address.raw = norm_raw # Update in place for now
            
            # 2. Generate Fingerprint
            fingerprint = self._generate_location_fingerprint(loc.address)
            
            if fingerprint not in merged:
                merged[fingerprint] = loc
            else:
                existing = merged[fingerprint]
                # Merge evidence
                existing.evidence.extend(loc.evidence)
                existing.internal_evidence.extend(loc.internal_evidence)
                existing.phones.extend(loc.phones)
                existing.emails.extend(loc.emails)
                existing.warnings.extend(loc.warnings)
                
                # Merge fields: Keep the one with more structured data
                if not existing.address.postal_code and loc.address.postal_code:
                    existing.address = loc.address
                elif len(loc.address.raw) > len(existing.address.raw) and "..." not in loc.address.raw:
                     pass

        # Recalculate scores for merged locations
        for loc in merged.values():
            loc.confidence = self.scoring_engine.calculate_field_score(loc.evidence)
            
        return list(merged.values())

    def _sanitize_final_locations(self, locations: list[Location]) -> list[Location]:
        """
        M6.1 Conservative Gatekeeper:
        Filters out locations that look like ISO standards, UI noise, or spam.
        """
        clean_locations = []
        
        # Blocklist for raw content
        raw_blocklist = [
            "visit our website", "visit the", "click here", "subscribe", 
            "newsletter", "email us", "connect with", "follow us",
            "iso 9001", "iso 14001", "iso 45001", "iso 50001",
            "policy", "rights reserved", "copyright"
        ]
        
        # Blocklist for Postal Codes (common False Positives)
        postal_blocklist = {"9001", "14001", "45001", "50001", "27001"}
        
        for loc in locations:
            raw = loc.address.raw.lower()
            postal = loc.address.postal_code
            
            # 1. Postal Code Check
            if postal and postal.replace(" ", "") in postal_blocklist:
                continue # Reject ISO number as postal code
                
            # 2. Raw Content Check
            if any(term in raw for term in raw_blocklist):
                # Conservative: if it has ISO or 'visit website', kill it.
                continue
                
            # 3. Nav/UI Noise Check
            if "home" in raw and "contact" in raw and not postal:
                # Likely a nav bar extracted as address
                continue
                
            clean_locations.append(loc)
            
        return clean_locations

    def _generate_location_fingerprint(self, address: Address) -> str:
        """
        Generates a canonical fingerprint for deduplication.
        Strategy:
        1. Postal Code + Street Number (Best)
        2. Street Number + Street Name Stem (Medium)
        3. Normalized Raw (Fallback)
        """
        postal = address.postal_code.strip().lower() if address.postal_code else ""
        
        # Extract street number and name if not present
        street_num = ""
        street_name = ""
        
        if address.street:
            match = re.match(r'^(\d+)\s+(.*)', address.street)
            if match:
                street_num = match.group(1)
                street_name = match.group(2).lower()
            else:
                street_name = address.street.lower()
        else:
            # Try regex on raw
            match = re.search(r'(\d+)\s+([a-z\s]+)', address.raw, re.I)
            if match:
                street_num = match.group(1)
                street_name = match.group(2).lower()

        if postal and street_num:
            return f"postal:{postal}|num:{street_num}"
        
        if street_num and street_name:
            # Simple stemming: take first word of street name
            stem = street_name.split()[0] if street_name else ""
            if len(stem) > 2:
                return f"street:{stem}|num:{street_num}"
        
        # Fallback
        return f"raw:{address.raw.lower()}"

    def _normalize_address(self, raw: str) -> str:
        norm = " ".join(raw.split()).strip()
        for pattern, replacement in ADDRESS_ABBREVIATIONS.items():
            norm = re.sub(pattern, replacement, norm, flags=re.I)
        norm = norm.rstrip("., ")
        return norm

    # --- Other Normalizers ---
    def _normalize_email(self, val: str) -> str:
        try:
            return (val or "").strip().lower()
        except Exception:
            return ""

    def _normalize_phone(self, val: str) -> str:
        try:
            return (val or "").strip()
        except Exception:
            return ""

    def _normalize_social(self, val: str) -> str:
        try:
            if not val: return ""
            parsed = urlparse(val)
            host = parsed.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            for platform, config in SOCIAL_PLATFORMS.items():
                if any(domain in host for domain in config["domains"]):
                    host = config["canonical_domain"]
                    break
            path = parsed.path.rstrip("/")
            path = path.lower()
            return urlunparse((parsed.scheme, host, path, "", "", ""))
        except Exception:
            return val.strip() if val else ""

    def _is_phone_plausible(self, val: str) -> bool:
        if not val: return False
        digits = re.sub(r'\D', '', val)
        if len(digits) < PHONE_MIN_DIGITS: return False
        counts = Counter(digits)
        if not counts: return False
        most_common_digit, count = counts.most_common(1)[0]
        if count / len(digits) > PHONE_MAX_REPETITION_RATIO: return False
        if val.startswith("+1000") or val.startswith("+000"): return False
        return True

    def _is_social_plausible(self, val: str) -> bool:
        try:
            if not val: return False
            val_lower = val.lower()
            parsed = urlparse(val_lower)
            path = parsed.path
            query = parsed.query or "" # Ensure query is str
            host_part = parsed.netloc
            for _, config in SOCIAL_PLATFORMS.items():
                if config["canonical_domain"] in host_part:
                    for pattern in config["blacklisted_paths"]:
                        if re.search(pattern, path):
                            return False
            if any(key + "=" in query for key in GENERIC_SHARING_QUERY_KEYS):
                if any(x in path for x in ["share", "tweet", "intent"]):
                    return False
            if path in ["", "/", "/home", "/intent"]:
                return False
            return True
        except Exception:
            return False

    def _refresh_governance(self, profile: OrganizationProfile):
        accepted_ev: set[tuple[str, str, str]] = set()
        internal_ev: list[Evidence] = []
        
        for c in (profile.phones + profile.emails + profile.social_links):
            for ev in c.evidence:
                accepted_ev.add((ev.source_url or "", ev.source_type, ev.snippet or ""))
            internal_ev.extend(c.internal_evidence)
            
        for loc in profile.locations:
            for ev in loc.evidence:
                accepted_ev.add((ev.source_url or "", ev.source_type, ev.snippet or ""))
            internal_ev.extend(loc.internal_evidence)
            
        profile.evidence = [
            Evidence(source_url=url, source_type=stype, snippet=snip) 
            for url, stype, snip in accepted_ev
        ]
        profile.internal_evidence = internal_ev
        
        score = self.scoring_engine.calculate_profile_score(profile)
        profile.confidence = Confidence(overall_score=score)

# Register strategy
registry.register("merger", "standard", ProfilePostProcessor)
