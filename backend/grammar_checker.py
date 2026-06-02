import requests
from typing import List, Dict, Optional
import logging
import re
from models import ProofreadingError, ErrorType, Severity

logger = logging.getLogger(__name__)

class LanguageToolChecker:
    """LanguageTool 语法检查器"""
    
    def __init__(self, api_url: str = "http://localhost:8081"):
        self.api_url = api_url
        self.enabled = self._check_connection()
    
    def _check_connection(self) -> bool:
        """检查连接"""
        try:
            response = requests.get(f"{self.api_url}/v2/languages", timeout=5)
            return response.status_code == 200
        except:
            logger.warning("LanguageTool 服务不可用，将跳过语法检查")
            return False
    
    def check_text(self, text: str, language: str = "zh-CN") -> List[Dict]:
        """使用 LanguageTool 检查文本"""
        if not self.enabled or not text.strip():
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/v2/check",
                params={
                    "text": text,
                    "language": language,
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("matches", [])
            else:
                logger.error(f"LanguageTool 返回错误: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"LanguageTool 请求失败: {e}")
            return []
    
    def convert_to_proofreading_error(self, para_index: int, match: Dict) -> Optional[ProofreadingError]:
        """将 LanguageTool 错误转换为 ProofreadingError"""
        try:
            error_type_map = {
                "GRAMMAR": ErrorType.GRAMMAR,
                "SPELLING": ErrorType.SPELLING,
                "PUNCTUATION": ErrorType.PUNCTUATION,
                "STYLE": ErrorType.STYLE,
            }
            
            rule_id = match.get("rule", {}).get("id", "UNKNOWN")
            error_type = error_type_map.get("GRAMMAR", ErrorType.GRAMMAR)
            
            issue_type = match.get("rule", {}).get("issueType", "")
            severity = Severity.MEDIUM
            if issue_type == "grammar":
                severity = Severity.HIGH
            elif issue_type == "spelling":
                severity = Severity.HIGH
            elif issue_type == "whitespace":
                severity = Severity.LOW
            
            replacements = match.get("replacements", [])
            suggestion = replacements[0]["value"] if replacements else ""
            
            return ProofreadingError(
                error_id=f"lt_{para_index}_{match.get('offset', 0)}",
                paragraph_index=para_index,
                start_position=match.get("offset", 0),
                end_position=match.get("offset", 0) + match.get("length", 0),
                error_type=error_type,
                severity=severity,
                original_text=match.get("context", {}).get("text", ""),
                suggestion=suggestion,
                explanation=match.get("message", ""),
                source="languagetool",
                confidence=0.9
            )
        except Exception as e:
            logger.error(f"转换错误失败: {e}")
            return None


class PatternChecker:
    """模式检查器 - 基于规则的检查"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> List[Dict]:
        """加载检查规则"""
        return [
            {
                "name": "连续空格",
                "pattern": r"  +",
                "error_type": ErrorType.FORMATTING,
                "severity": Severity.LOW,
                "suggestion": " ",
                "explanation": "检测到多个连续空格"
            },
            {
                "name": "中英文之间空格",
                "pattern": r"(?<=[a-zA-Z0-9])[\u4e00-\u9fff]|[\u4e00-\u9fff](?=[a-zA-Z0-9])",
                "error_type": ErrorType.STYLE,
                "severity": Severity.LOW,
                "suggestion": " ",
                "explanation": "中英文之间应该有空格"
            },
            {
                "name": "行首空格",
                "pattern": r"^\s+",
                "error_type": ErrorType.FORMATTING,
                "severity": Severity.LOW,
                "suggestion": "",
                "explanation": "行首不应该有空格"
            },
            {
                "name": "标点符号前空格",
                "pattern": r"\s+([。，！？；：、])",
                "error_type": ErrorType.FORMATTING,
                "severity": Severity.MEDIUM,
                "suggestion": "$1",
                "explanation": "中文标点符号前不应该有空格"
            },
            {
                "name": "重复词汇",
                "pattern": r"(\S+)(\1+)",
                "error_type": ErrorType.STYLE,
                "severity": Severity.MEDIUM,
                "suggestion": "$1",
                "explanation": "检测到重复的词汇"
            }
        ]
    
    def check_text(self, text: str, para_index: int) -> List[ProofreadingError]:
        """检查文本中的模式"""
        errors = []
        
        for pattern_rule in self.patterns:
            try:
                matches = re.finditer(pattern_rule["pattern"], text)
                for match in matches:
                    error = ProofreadingError(
                        error_id=f"pat_{para_index}_{match.start()}",
                        paragraph_index=para_index,
                        start_position=match.start(),
                        end_position=match.end(),
                        error_type=pattern_rule["error_type"],
                        severity=pattern_rule["severity"],
                        original_text=match.group(),
                        suggestion=match.expand(pattern_rule["suggestion"]),
                        explanation=pattern_rule["explanation"],
                        source="pattern",
                        confidence=0.95
                    )
                    errors.append(error)
            except Exception as e:
                logger.error(f"模式检查失败 {pattern_rule['name']}: {e}")
        
        return errors
