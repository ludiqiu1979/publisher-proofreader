from typing import List, Dict
import logging
import re
from models import ProofreadingError, ErrorType, Severity

logger = logging.getLogger(__name__)

class StyleChecker:
    """风格和格式检查器"""
    
    def __init__(self, publisher_rules: Dict = None):
        self.publisher_rules = publisher_rules or self._default_rules()
    
    def _default_rules(self) -> Dict:
        """默认出版社规则"""
        return {
            "max_paragraph_length": 500,
            "check_consistency": True,
            "check_terminology": True,
            "check_formatting": True,
            "terminology_dict": {
                "人工智能": ["AI", "AI技术"],
                "机器学习": ["ML"],
            }
        }
    
    def check_paragraph_length(self, text: str, para_index: int) -> List[ProofreadingError]:
        """检查段落长度"""
        errors = []
        max_length = self.publisher_rules.get("max_paragraph_length", 500)
        
        if len(text) > max_length:
            error = ProofreadingError(
                error_id=f"length_{para_index}",
                paragraph_index=para_index,
                start_position=0,
                end_position=len(text),
                error_type=ErrorType.FORMATTING,
                severity=Severity.LOW,
                original_text=text[:50] + "...",
                suggestion="建议将段落拆分为多个较短的段落",
                explanation=f"段落长度为 {len(text)} 字符，超过最大限制 {max_length}",
                source="style",
                confidence=1.0
            )
            errors.append(error)
        
        return errors
    
    def check_formatting(self, text: str, para_index: int) -> List[ProofreadingError]:
        """检查格式问题"""
        errors = []
        
        if text.startswith(" "):
            error = ProofreadingError(
                error_id=f"indent_{para_index}",
                paragraph_index=para_index,
                start_position=0,
                end_position=1,
                error_type=ErrorType.FORMATTING,
                severity=Severity.MEDIUM,
                original_text=" " + text[1:10],
                suggestion=text[1:10],
                explanation="段落不应以空格开头",
                source="style",
                confidence=1.0
            )
            errors.append(error)
        
        spaces_match = re.search(r"  +", text)
        if spaces_match:
            error = ProofreadingError(
                error_id=f"spaces_{para_index}",
                paragraph_index=para_index,
                start_position=spaces_match.start(),
                end_position=spaces_match.end(),
                error_type=ErrorType.FORMATTING,
                severity=Severity.LOW,
                original_text=spaces_match.group(),
                suggestion=" ",
                explanation="检测到多个连续空格",
                source="style",
                confidence=1.0
            )
            errors.append(error)
        
        if text.rstrip() != text:
            error = ProofreadingError(
                error_id=f"trailing_{para_index}",
                paragraph_index=para_index,
                start_position=len(text.rstrip()),
                end_position=len(text),
                error_type=ErrorType.FORMATTING,
                severity=Severity.LOW,
                original_text=text[-5:],
                suggestion=text.rstrip()[-5:],
                explanation="行尾不应有空格",
                source="style",
                confidence=1.0
            )
            errors.append(error)
        
        return errors
    
    def check_terminology(self, text: str, para_index: int) -> List[ProofreadingError]:
        """检查术语一致性"""
        errors = []
        
        terminology_dict = self.publisher_rules.get("terminology_dict", {})
        
        for preferred_term, alternatives in terminology_dict.items():
            for alt_term in alternatives:
                if alt_term in text:
                    error = ProofreadingError(
                        error_id=f"term_{para_index}_{alt_term}",
                        paragraph_index=para_index,
                        start_position=text.find(alt_term),
                        end_position=text.find(alt_term) + len(alt_term),
                        error_type=ErrorType.TERMINOLOGY,
                        severity=Severity.MEDIUM,
                        original_text=alt_term,
                        suggestion=preferred_term,
                        explanation=f"应使用统一术语 '{preferred_term}' 代替 '{alt_term}'",
                        source="style",
                        confidence=0.95
                    )
                    errors.append(error)
        
        return errors
    
    def check_punctuation(self, text: str, para_index: int) -> List[ProofreadingError]:
        """检查标点符号使用"""
        errors = []
        
        punct_with_space = re.finditer(r"\s+([。，、；：？！])", text)
        for match in punct_with_space:
            error = ProofreadingError(
                error_id=f"punct_{para_index}_{match.start()}",
                paragraph_index=para_index,
                start_position=match.start(),
                end_position=match.end(),
                error_type=ErrorType.PUNCTUATION,
                severity=Severity.MEDIUM,
                original_text=match.group(),
                suggestion=match.group(1),
                explanation="中文标点符号前不应有空格",
                source="style",
                confidence=1.0
            )
            errors.append(error)
        
        no_space_pattern = re.finditer(r"([\u4e00-\u9fff])([a-zA-Z0-9])", text)
        for match in no_space_pattern:
            error = ProofreadingError(
                error_id=f"spacing_{para_index}_{match.start()}",
                paragraph_index=para_index,
                start_position=match.start(),
                end_position=match.end(),
                error_type=ErrorType.STYLE,
                severity=Severity.LOW,
                original_text=match.group(),
                suggestion=f"{match.group(1)} {match.group(2)}",
                explanation="中文和英文/数字之间应有空格",
                source="style",
                confidence=0.9
            )
            errors.append(error)
        
        return errors
