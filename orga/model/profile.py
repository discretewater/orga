from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from .types import ContactKind, WarningSeverity
from .document import Warning

class Evidence(BaseModel):
    """
    Represents the evidence source for an extracted field.
    """
    source_url: Optional[str] = Field(None, description="Source URL")
    source_type: str = Field(..., description="Source type (e.g., html_attr_tel, jsonld_address)")
    snippet: Optional[str] = Field(None, description="Relevant text snippet or raw data")
    extractor_name: Optional[str] = Field(None, description="Name of the extractor")
    strategy_name: Optional[str] = Field(None, description="Name of the strategy")
    confidence_score: float = Field(0.0, description="Confidence score for this specific piece of evidence")

class Confidence(BaseModel):
    """
    Represents confidence scoring.
    """
    overall_score: float = Field(0.0, ge=0.0, le=1.0, description="Overall confidence")
    field_scores: Dict[str, float] = Field(default_factory=dict, description="Independent confidence for each field")

class Address(BaseModel):
    """
    Represents a physical address.
    """
    raw: str = Field(..., description="Original raw address string (Must be preserved)")
    street: Optional[str] = Field(None, description="Street address")
    unit: Optional[str] = Field(None, description="Unit/Room number")
    city: Optional[str] = Field(None, description="City")
    region: Optional[str] = Field(None, description="State/Province/Region")
    postal_code: Optional[str] = Field(None, description="Postal code")
    country: Optional[str] = Field(None, description="Country")

class Contact(BaseModel):
    """
    Represents contact information.
    """
    kind: ContactKind = Field(..., description="Type of contact")
    value: str = Field(..., description="Value (e.g., phone number, email address)")
    label: Optional[str] = Field(None, description="Label (e.g., 'Support', 'Sales')")
    confidence: float = Field(0.0, description="Confidence score")
    evidence: List[Evidence] = Field(default_factory=list, description="Accepted evidence chain")
    internal_evidence: List[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")

class Location(BaseModel):
    """
    Represents a physical location of an organization.
    """
    label: Optional[str] = Field(None, description="Location label (e.g., 'HQ')")
    address: Address = Field(..., description="Address information")
    phones: List[Contact] = Field(default_factory=list, description="Phones for this location")
    emails: List[Contact] = Field(default_factory=list, description="Emails for this location")
    map_links: List[str] = Field(default_factory=list, description="Map links")
    confidence: float = Field(0.0, description="Confidence score")
    evidence: List[Evidence] = Field(default_factory=list, description="Accepted evidence chain")
    internal_evidence: List[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")
    warnings: List[Warning] = Field(default_factory=list, description="Warnings specific to this location")

class OrganizationProfile(BaseModel):
    """
    Core Model: Organization Profile.
    """
    name: Optional[str] = Field(None, description="Organization name")
    aliases: List[str] = Field(default_factory=list, description="List of aliases")
    org_type: Optional[str] = Field(None, description="Organization type")
    description: Optional[str] = Field(None, description="Description")
    
    locations: List[Location] = Field(default_factory=list, description="List of locations")
    
    phones: List[Contact] = Field(default_factory=list, description="List of phones (Org-level)")
    emails: List[Contact] = Field(default_factory=list, description="List of emails (Org-level)")
    contact_form_url: Optional[str] = Field(None, description="Contact form URL")
    social_links: List[Contact] = Field(default_factory=list, description="Social media links")
    
    categories: List[str] = Field(default_factory=list, description="Business categories")
    services: List[str] = Field(default_factory=list, description="Services provided")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    
    observed_at: Optional[datetime] = Field(None, description="Observation timestamp")
    evidence: List[Evidence] = Field(default_factory=list, description="Global accepted evidence chain")
    internal_evidence: List[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")
    confidence: Optional[Confidence] = Field(None, description="Confidence information")
    warnings: List[Warning] = Field(default_factory=list, description="List of warnings")
    debug_info: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic information (only populated in debug mode)")
    schema_version: str = Field("0.1.0", description="Schema version")
