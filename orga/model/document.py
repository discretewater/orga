from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .types import SourceKind, WarningSeverity


class Warning(BaseModel):
    """
    Represents a warning or error message generated during processing.
    """
    code: str = Field(..., description="Error or warning code, e.g., FETCH_TIMEOUT")
    message: str = Field(..., description="Human-readable message")
    severity: WarningSeverity = Field(default=WarningSeverity.WARNING, description="Severity level")
    related_field: str | None = Field(None, description="Associated field name")
    source_url: str | None = Field(None, description="Source URL generating this warning")

class Document(BaseModel):
    """
    Represents a fetched webpage or document. The core input for parsing.
    """
    url: str = Field(..., description="Original URL")
    final_url: str | None = Field(None, description="Final URL after redirects")
    content: str = Field(..., description="Document content (usually HTML text)")
    content_type: str = Field("text/html", description="MIME type")
    encoding: str | None = Field(None, description="Character encoding")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="Time of fetch")
    status_code: int = Field(200, description="HTTP status code")
    headers_summary: dict[str, str] = Field(default_factory=dict, description="Key response headers summary")
    fetch_warnings: list[Warning] = Field(default_factory=list, description="Warnings generated during fetch phase")
    source_kind: SourceKind = Field(default=SourceKind.HTTP_FETCH, description="Source kind")

    @field_validator("content")
    def content_must_not_be_empty(cls, v: str) -> str:
        if not v:
            # Allow empty content in specific cases (like HEAD requests), but parsing usually requires content.
            # To pass test_document_validation_error, we retain the non-empty validation here.
            raise ValueError("Document content cannot be empty")
        return v

class DocumentBundle(BaseModel):
    """
    Represents a bundle of related documents for the same organization (e.g., home page, contact page, about page).
    """
    entry_url: str = Field(..., description="Entry URL, usually the homepage")
    documents: list[Document] = Field(default_factory=list, description="List of documents")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="Time of fetch")
