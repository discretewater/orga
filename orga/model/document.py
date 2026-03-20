from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime
from .types import SourceKind, WarningSeverity

class Warning(BaseModel):
    """
    表示处理过程中产生的警告或错误信息。
    """
    code: str = Field(..., description="错误或警告代码，例如 FETCH_TIMEOUT")
    message: str = Field(..., description="人类可读的消息")
    severity: WarningSeverity = Field(default=WarningSeverity.WARNING, description="严重程度")
    related_field: Optional[str] = Field(None, description="关联的字段名")
    source_url: Optional[str] = Field(None, description="产生该警告的源 URL")

class Document(BaseModel):
    """
    表示一个被获取的网页或文档。是解析的核心输入。
    """
    url: str = Field(..., description="原始 URL")
    final_url: Optional[str] = Field(None, description="重定向后的最终 URL")
    content: str = Field(..., description="文档内容（通常是 HTML 文本）")
    content_type: str = Field("text/html", description="MIME 类型")
    encoding: Optional[str] = Field(None, description="字符编码")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="获取时间")
    status_code: int = Field(200, description="HTTP 状态码")
    headers_summary: Dict[str, str] = Field(default_factory=dict, description="关键响应头摘要")
    fetch_warnings: List[Warning] = Field(default_factory=list, description="获取阶段产生的警告")
    source_kind: SourceKind = Field(default=SourceKind.HTTP_FETCH, description="来源类型")

    @field_validator("content")
    def content_must_not_be_empty(cls, v: str) -> str:
        if not v:
            # 允许特定情况下的空内容（如 HEAD 请求），但通常解析需要内容
            # 这里为了通过测试 test_document_validation_error，我们保留不为空的校验
            raise ValueError("Document content cannot be empty")
        return v

class DocumentBundle(BaseModel):
    """
    表示同一组织的一组相关文档（例如首页、联系页、关于页）。
    """
    entry_url: str = Field(..., description="入口 URL，通常是首页")
    documents: List[Document] = Field(default_factory=list, description="文档列表")
    fetched_at: datetime = Field(default_factory=datetime.utcnow, description="获取时间")
