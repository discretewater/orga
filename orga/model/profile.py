from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .document import Warning
from .types import ContactKind


class Evidence(BaseModel):
    """
    Represents the evidence source for an extracted field.
    """
    source_url: str | None = Field(None, description="Source URL")
    source_type: str = Field(..., description="Source type (e.g., html_attr_tel, jsonld_address)")
    snippet: str | None = Field(None, description="Relevant text snippet or raw data")
    extractor_name: str | None = Field(None, description="Name of the extractor")
    strategy_name: str | None = Field(None, description="Name of the strategy")
    confidence_score: float = Field(0.0, description="Confidence score for this specific piece of evidence")

class Confidence(BaseModel):
    """
    Represents confidence scoring.
    """
    overall_score: float = Field(0.0, ge=0.0, le=1.0, description="Overall confidence")
    field_scores: dict[str, float] = Field(default_factory=dict, description="Independent confidence for each field")

class Address(BaseModel):
    """
    Represents a physical address.
    """
    raw: str = Field(..., description="Original raw address string (Must be preserved)")
    street: str | None = Field(None, description="Street address")
    unit: str | None = Field(None, description="Unit/Room number")
    city: str | None = Field(None, description="City")
    region: str | None = Field(None, description="State/Province/Region")
    postal_code: str | None = Field(None, description="Postal code")
    country: str | None = Field(None, description="Country")

class Contact(BaseModel):
    """
    Represents contact information.
    """
    kind: ContactKind = Field(..., description="Type of contact")
    value: str = Field(..., description="Value (e.g., phone number, email address)")
    label: str | None = Field(None, description="Label (e.g., 'Support', 'Sales')")
    confidence: float = Field(0.0, description="Confidence score")
    evidence: list[Evidence] = Field(default_factory=list, description="Accepted evidence chain")
    internal_evidence: list[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")

class Location(BaseModel):
    """
    Represents a physical location of an organization.
    """
    label: str | None = Field(None, description="Location label (e.g., 'HQ')")
    address: Address = Field(..., description="Address information")
    phones: list[Contact] = Field(default_factory=list, description="Phones for this location")
    emails: list[Contact] = Field(default_factory=list, description="Emails for this location")
    map_links: list[str] = Field(default_factory=list, description="Map links")
    confidence: float = Field(0.0, description="Confidence score")
    evidence: list[Evidence] = Field(default_factory=list, description="Accepted evidence chain")
    internal_evidence: list[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")
    warnings: list[Warning] = Field(default_factory=list, description="Warnings specific to this location")

class OrganizationProfile(BaseModel):
    """
    Core Model: Organization Profile.
    """
    name: str | None = Field(None, description="Organization name")
    aliases: list[str] = Field(default_factory=list, description="List of aliases")
    org_type: str | None = Field(None, description="Organization type")
    description: str | None = Field(None, description="Description")
    
    locations: list[Location] = Field(default_factory=list, description="List of locations")
    
    phones: list[Contact] = Field(default_factory=list, description="List of phones (Org-level)")
    emails: list[Contact] = Field(default_factory=list, description="List of emails (Org-level)")
    contact_form_url: str | None = Field(None, description="Contact form URL")
    social_links: list[Contact] = Field(default_factory=list, description="Social media links")
    
    categories: list[str] = Field(default_factory=list, description="Business categories")
    services: list[str] = Field(default_factory=list, description="Services provided")
    keywords: list[str] = Field(default_factory=list, description="Keywords")
    
    observed_at: datetime | None = Field(None, description="Observation timestamp")
    evidence: list[Evidence] = Field(default_factory=list, description="Global accepted evidence chain")
    internal_evidence: list[Evidence] = Field(default_factory=list, description="Rejected or debugging evidence")
    confidence: Confidence | None = Field(None, description="Confidence information")
    warnings: list[Warning] = Field(default_factory=list, description="List of warnings")
    debug_info: dict[str, Any] = Field(default_factory=dict, description="Diagnostic information (only populated in debug mode)")
    schema_version: str = Field("0.1.2", description="Schema version")
