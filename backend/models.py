from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class ErrorType(str, Enum):
    """错误类型"""
    GRAMMAR = "grammar"
    SPELLING = "spelling"
    PUNCTUATION = "punctuation"
    STYLE = "style"
    CONSISTENCY = "consistency"
    FORMATTING = "formatting"
    TERMINOLOGY = "terminology"
    LOGIC = "logic"

class Severity(str, Enum):
    """严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ProofreadingError(BaseModel):
    """审校错误"""
    error_id: str
    paragraph_index: int
    start_position: int
    end_position: int
    error_type: ErrorType
    severity: Severity
    original_text: str
    suggestion: str
    explanation: str
    source: str
    confidence: float

class DocumentAnalysis(BaseModel):
    """文档分析结果"""
    total_errors: int
    errors_by_type: Dict[str, int]
    errors_by_severity: Dict[str, int]
    errors: List[ProofreadingError]
    processing_time: float
    statistics: Dict

class DocumentRequest(BaseModel):
    """文档处理请求"""
    file_name: str
    author_name: str = "Proofreader"
    check_types: List[str] = ["grammar", "spelling", "style", "consistency"]
    output_format: str = "docx"
    track_changes: bool = True

class ProcessingResult(BaseModel):
    """处理结果"""
    status: str
    file_path: Optional[str] = None
    analysis: Optional[DocumentAnalysis] = None
    message: str
    timestamp: datetime = None

class RevisionItem(BaseModel):
    """修订项"""
    revision_id: str
    paragraph_index: int
    revision_type: str
    original_text: str
    new_text: str
    author: str
    timestamp: datetime
    comment: Optional[str] = None

class DocumentMetadata(BaseModel):
    """文档元数据"""
    filename: str
    upload_time: datetime
    total_paragraphs: int
    total_words: int
    total_sentences: int
    language: str = "zh_CN"
