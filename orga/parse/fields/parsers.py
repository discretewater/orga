import re
from abc import ABC, abstractmethod
from typing import Any

import phonenumbers
from phonenumbers import PhoneNumberMatcher

from orga.model import Address, Contact, ContactKind, Document, Evidence, Location
from orga.parse.fields.address_scorer import AddressScorer
from orga.registry import registry


class BaseFieldParser(ABC):
    """
    Base class for field parsers.
    """
    @abstractmethod
    def parse(self, doc: Document) -> list[Any]:
        pass

class ContactParser(BaseFieldParser):
    """
    Parser for contact information.
    Supports: Email, Phone, Social Links.
    """
    
    IGNORED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'js', 'css', 'woff', 'woff2', 'ttf', 'eot'}

    def parse(self, doc: Document) -> list[Contact]:
        contacts = []
        contacts.extend(self._extract_emails(doc))
        contacts.extend(self._extract_phones(doc))
        contacts.extend(self._extract_socials(doc))
        return contacts

    def _extract_emails(self, doc: Document) -> list[Contact]:
        try:
            email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
            from selectolax.parser import HTMLParser
            tree = HTMLParser(doc.content)
            
            found = set()
            results = []

            for node in tree.css('a[href^="mailto:"]'):
                href = node.attributes.get("href") or ""
                # Defensive check
                if not href: continue
                email = href.replace("mailto:", "").split("?")[0].strip()
                email = email.rstrip(".,;:)") 
                if self._is_valid_email(email) and email not in found:
                    found.add(email)
                    results.append(Contact(
                        kind=ContactKind.EMAIL,
                        value=email,
                        confidence=0.9,
                        evidence=[Evidence(source_type="html_attr_mailto", snippet=href, source_url=doc.url, confidence_score=0.9)]
                    ))

            for match in email_pattern.finditer(doc.content):
                email = match.group()
                for noise in ["Please", "Contact", "Tel", "Fax"]:
                    if email.endswith(noise):
                        email = email[:-len(noise)]
                
                if self._is_valid_email(email) and email not in found:
                    found.add(email)
                    results.append(Contact(
                        kind=ContactKind.EMAIL,
                        value=email,
                        confidence=0.7,
                        evidence=[Evidence(source_type="regex_text", snippet=email, source_url=doc.url, confidence_score=0.7)]
                    ))
                    
            return results
        except Exception:
            return []

    def _is_valid_email(self, email: str) -> bool:
        if not email or len(email) > 100: return False
        if "." not in email: return False
        
        try:
            if "." in email:
                ext = email.rsplit(".", 1)[-1].lower()
                if ext in self.IGNORED_EXTENSIONS:
                    return False
            if "sentry" in email or "example.com" in email:
                return False
            return True
        except Exception:
            return False

    def _extract_phones(self, doc: Document) -> list[Contact]:
        try:
            results = []
            found_numbers = set()
            from selectolax.parser import HTMLParser
            tree = HTMLParser(doc.content)
            
            for node in tree.css('a[href^="tel:"]'):
                href = node.attributes.get("href") or ""
                if not href: continue
                raw_phone = href.replace("tel:", "").strip()
                phone = self._validate_and_format_phone(raw_phone)
                if phone and phone not in found_numbers:
                    found_numbers.add(phone)
                    results.append(Contact(
                        kind=ContactKind.PHONE,
                        value=phone,
                        confidence=0.9,
                        evidence=[Evidence(source_type="html_attr_tel", snippet=href, source_url=doc.url, confidence_score=0.9)]
                    ))

            if tree.body:
                text_content = tree.body.text(separator=" ")
            else:
                text_content = re.sub(r'<[^>]+>', ' ', doc.content)
            
            for match in PhoneNumberMatcher(text_content, "US"):
                raw_phone = match.raw_string
                if re.match(r'^\d{4}-\d{2}-\d{2}$', raw_phone.strip()): continue
                if re.match(r'\b10\.\d{4}/', raw_phone.strip()): continue
                if re.match(r'\d+\.\d+\.\d+\.\d+', raw_phone.strip()): continue

                phone = phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164)
                if phone and phone not in found_numbers:
                    found_numbers.add(phone)
                    results.append(Contact(
                        kind=ContactKind.PHONE,
                        value=phone,
                        confidence=0.6,
                        evidence=[Evidence(source_type="text_matcher_validated", snippet=raw_phone, source_url=doc.url, confidence_score=0.6)]
                    ))
            return results
        except Exception:
            return []

    def _validate_and_format_phone(self, raw: str) -> str | None:
        try:
            parsed = phonenumbers.parse(raw, "US") 
            if phonenumbers.is_possible_number(parsed):
                 return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass
        return None

    def _extract_socials(self, doc: Document) -> list[Contact]:
        try:
            from selectolax.parser import HTMLParser
            tree = HTMLParser(doc.content)
            social_domains = ["twitter.com", "linkedin.com", "facebook.com", "instagram.com", "github.com", "youtube.com"]
            results = []
            
            for node in tree.css('a[href]'):
                href = node.attributes.get("href") or ""
                if not href: continue
                if any(d in href for d in social_domains):
                    results.append(Contact(
                        kind=ContactKind.SOCIAL,
                        value=href,
                        confidence=0.8,
                        evidence=[Evidence(source_type="html_attr_social", snippet=href, source_url=doc.url, confidence_score=0.8)]
                    ))
            return results
        except Exception:
            return []

class AddressParser(BaseFieldParser):
    """
    Address parser with JSON-LD and Advanced Heuristic support.
    """
    
    # Moved Patterns to AddressScorer mostly, but kept some for processing
    POSTAL_US = r'\b\d{5}(?:-\d{4})?\b'
    POSTAL_UK = r'\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b'
    POSTAL_CA = r'\b[A-Z]\d[A-Z] ?\d[A-Z]\d\b'
    
    STREET_TYPES = r'(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Plaza|Square|Sq|Court|Ct|Circle|Cir|Highway|Hwy|House|Building)'
    
    TERMINATION_SIGNALS = [
        r'^\s*Tel:', r'^\s*Phone:', r'^\s*Call:', r'^\s*Fax:',
        r'^\s*Email:', r'^\s*mailto:',
        r'^\s*Copyright', r'^\s*©', r'^\s*All rights reserved',
        r'^\s*Open:', r'^\s*Hours:',
        r'^\s*Follow us', r'^\s*Connect with',
        r'^\s*Map', r'^\s*Directions',
        r'^\s*Privacy Policy', r'^\s*Terms of Use',
        r'^\s*Menu', r'^\s*Nav', r'^\s*Subscribe', r'^\s*Search'
    ]
    
    NEGATIVE_PATTERNS = [
        r'\bDOI:\s*10\.', r'\bISSN\b', r'\bISBN\b',
        r'\bGrant No\.', r'\bSupported by\b',
        r'\bPolicy\b', r'\bStatement\b', 
        r'\bRights Reserved\b', r'\bCopyright\b', r'©\s*\d{4}'
    ]

    def __init__(self):
        self.scorer = AddressScorer()

    def parse(self, doc: Document) -> list[Location]:
        locations = []
        locations.extend(self._extract_json_ld(doc))
        locations.extend(self._extract_heuristic_dom(doc))
        return locations

    def _extract_json_ld(self, doc: Document) -> list[Location]:
        import extruct
        try:
            data = extruct.extract(doc.content, base_url=doc.url, syntaxes=['json-ld'])
            results = []
            for item in data.get('json-ld', []):
                if item.get('@type') in ['Organization', 'LocalBusiness', 'Corporation', 'Hospital', 'EducationalOrganization']:
                    addr = item.get('address')
                    if addr:
                        address_obj = None
                        if isinstance(addr, dict) and addr.get('@type') == 'PostalAddress':
                            raw = f"{addr.get('streetAddress', '')}, {addr.get('addressLocality', '')}"
                            address_obj = Address(
                                raw=raw,
                                street=addr.get('streetAddress'),
                                city=addr.get('addressLocality'),
                                postal_code=addr.get('postalCode'),
                                country=addr.get('addressCountry')
                            )
                        elif isinstance(addr, str):
                             address_obj = self._structure_address(addr)
                        
                        if address_obj:
                            results.append(Location(
                                address=address_obj,
                                confidence=1.0,
                                evidence=[Evidence(source_type="jsonld_address", snippet=address_obj.raw, source_url=doc.url, confidence_score=1.0)]
                            ))
            return results
        except Exception:
            return []

    def _extract_heuristic_dom(self, doc: Document) -> list[Location]:
        try:
            from selectolax.parser import HTMLParser
            tree = HTMLParser(doc.content)
            results = []
            
            zones = [
                ('footer', 1.2), ('.footer', 1.2), ('#footer', 1.2),
                ('.contact', 1.1), ('#contact', 1.1), 
                ('.address', 1.1), ('address', 1.1),
                ('body', 1.0)
            ]
            
            # We reuse regex for processing buffer, scoring happens in Scorer
            postal_pattern = re.compile(f'(?:{self.POSTAL_US}|{self.POSTAL_UK}|{self.POSTAL_CA})', re.IGNORECASE)
            street_pattern = re.compile(r'\d+\s+[\w\s,.-]+' + self.STREET_TYPES, re.IGNORECASE)
            termination_regex = re.compile('|'.join(self.TERMINATION_SIGNALS), re.IGNORECASE)
            negative_regex = re.compile('|'.join(self.NEGATIVE_PATTERNS), re.IGNORECASE)

            seen_raw = set()

            for selector, score_boost in zones:
                for node in tree.css(selector):
                    text = node.text(separator="\n", strip=True) or ""
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    
                    buffer = []
                    for line in lines:
                        if negative_regex.search(line):
                            buffer = []
                            continue

                        if termination_regex.search(line):
                            self._process_buffer(buffer, postal_pattern, street_pattern, results, seen_raw, selector, doc)
                            buffer = []
                            continue
                        
                        buffer.append(line)
                        if len(buffer) > 4:
                            self._process_buffer(buffer, postal_pattern, street_pattern, results, seen_raw, selector, doc)
                            buffer.pop(0) 
                    
                    if buffer:
                        self._process_buffer(buffer, postal_pattern, street_pattern, results, seen_raw, selector, doc)

            return results
        except Exception:
            return []

    def _process_buffer(self, buffer: list[str], postal_regex, street_regex, results: list[Location], seen: set, zone_name: str, doc: Document):
        if not buffer: return
        
        combined = ", ".join(buffer)
        if re.search(r'Home.*Contact.*About', combined, re.I): return

        # Pre-check for validity (Candidate Admission)
        has_street = street_regex.search(combined)
        has_postal = postal_regex.search(combined)
        
        # Valid Candidate Check
        is_valid_candidate = (has_street and has_postal) or (has_street and zone_name != 'body')
        
        if is_valid_candidate:
            if combined not in seen:
                # Score Candidate
                score, breakdown = self.scorer.calculate_score(combined, {"zone": zone_name})
                
                # Pruning Threshold (2.0 = Base 1 + Street 1)
                if score >= 2.0:
                    addr_obj = self._structure_address(combined)
                    # Normalize score to 0.0 - 1.0 range for Confidence model
                    # Max possible score is around 5.0 (Base 1 + Postal 2 + Street 1 + Zone 1)
                    normalized_conf = min(score / 5.0, 1.0)
                    
                    results.append(Location(
                        address=addr_obj,
                        confidence=normalized_conf, 
                        evidence=[Evidence(
                            source_type="heuristic_text", 
                            snippet=combined, 
                            source_url=doc.url, 
                            confidence_score=normalized_conf
                        )]
                    ))
                    seen.add(combined)

    def _structure_address(self, raw: str) -> Address:
        """
        Attempt to extract structured fields from raw string.
        """
        addr = Address(raw=raw)
        
        postal_match = re.search(f'(?:{self.POSTAL_US}|{self.POSTAL_UK}|{self.POSTAL_CA})', raw, re.IGNORECASE)
        if postal_match:
            addr.postal_code = postal_match.group().strip()
            
        street_match = re.search(r'^(\d+\s+[\w\s,.-]+' + self.STREET_TYPES + r')', raw, re.IGNORECASE)
        if street_match:
            addr.street = street_match.group(1).strip().rstrip(",")
            
        if addr.street and addr.postal_code:
            remain = raw.replace(addr.street, "").replace(addr.postal_code, "")
            remain = re.sub(r'^[,\s]+', '', remain)
            remain = re.sub(r'[,\s]+$', '', remain)
            
            parts = [p.strip() for p in remain.split(",") if p.strip()]
            
            if parts and parts[0].upper() in ["NW", "NE", "SW", "SE", "N", "S", "E", "W"]:
                parts.pop(0)
                
            if parts:
                addr.city = parts[0]
                if len(parts) > 1:
                    addr.region = parts[1]
        
        return addr

registry.register("parser", "contact", ContactParser)
registry.register("parser", "address", AddressParser)
