from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import asyncio
import logging
from datetime import datetime
import json
import uuid

from config import settings
from models import (
    DocumentRequest, ProcessingResult, DocumentAnalysis, 
    ErrorType, Severity, DocumentMetadata
)
from document_processor import DocumentProcessor
from grammar_checker import LanguageToolChecker, PatternChecker
from llm_integration import OllamaLLMChecker
from revision_tracker import RevisionTracker
from style_checker import StyleChecker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Path(settings.UPLOAD_DIR).mkdir(exist_ok=True)
Path(settings.OUTPUT_DIR).mkdir(exist_ok=True)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="出版社审校系统 - 支持 Word 文档、LLM 检查、修订跟踪"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

language_tool_checker = LanguageToolChecker(settings.LANGUAGETOOL_URL)
pattern_checker = PatternChecker()
style_checker = StyleChecker(settings.PUBLISHER_RULES)

if settings.LLM_TYPE == "ollama":
    llm_checker = OllamaLLMChecker(
        settings.OLLAMA_API_URL,
        settings.OLLAMA_MODEL
    )
else:
    llm_checker = None

processing_jobs = {}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "language_tool": language_tool_checker.enabled,
            "llm": llm_checker.enabled if llm_checker else False,
        }
    }


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    author_name: str = "Proofreader",
    background_tasks: BackgroundTasks = None
):
    """上传 Word 文档进行审校"""
    try:
        if not file.filename.endswith(('.docx', '.doc')):
            raise HTTPException(
                status_code=400,
                detail="只支持 .docx 或 .doc 格式的 Word 文档"
            )
        
        job_id = str(uuid.uuid4())
        file_path = Path(settings.UPLOAD_DIR) / f"{job_id}_{file.filename}"
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"文件已上传: {file_path}")
        
        if background_tasks:
            background_tasks.add_task(
                process_document_async,
                job_id=job_id,
                file_path=str(file_path),
                author_name=author_name
            )
        else:
            await process_document_async(job_id, str(file_path), author_name)
        
        return {
            "status": "processing",
            "job_id": job_id,
            "message": "文档正在处理中..."
        }
        
    except Exception as e:
        logger.error(f"上传文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """获取处理任务状态"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return processing_jobs[job_id]


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """下载审校后的 Word 文档"""
    try:
        if job_id not in processing_jobs:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        job = processing_jobs[job_id]
        
        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail="任务未完成或失败"
            )
        
        output_file = job.get("output_file")
        
        if not output_file or not Path(output_file).exists():
            raise HTTPException(status_code=404, detail="输出文件不存在")
        
        return FileResponse(
            output_file,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=Path(output_file).name
        )
        
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analysis/{job_id}")
async def get_analysis(job_id: str):
    """获取审校分析结果"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    job = processing_jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail="任务未完成"
        )
    
    return job.get("analysis")


async def process_document_async(job_id: str, file_path: str, author_name: str):
    """异步处理文档"""
    try:
        start_time = datetime.now()
        processing_jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "message": "正在初始化...",
            "start_time": start_time.isoformat()
        }
        
        doc_processor = DocumentProcessor(file_path)
        doc_processor.enable_track_changes(author_name)
        
        doc_stats = doc_processor.get_document_stats()
        paragraphs = doc_processor.get_paragraphs_text()
        
        logger.info(f"文档统计: {doc_stats}")
        
        all_errors = []
        
        if language_tool_checker.enabled:
            logger.info("开始 LanguageTool 检查...")
            processing_jobs[job_id]["message"] = "进行语法检查中..."
            processing_jobs[job_id]["progress"] = 20
            
            for para_idx, text in enumerate(paragraphs):
                if text.strip():
                    matches = language_tool_checker.check_text(text, "zh-CN")
                    for match in matches:
                        error = language_tool_checker.convert_to_proofreading_error(
                            para_idx, match
                        )
                        if error:
                            all_errors.append(error)
        
        logger.info("开始模式检查...")
        processing_jobs[job_id]["message"] = "进行格式检查中..."
        processing_jobs[job_id]["progress"] = 40
        
        for para_idx, text in enumerate(paragraphs):
            if text.strip():
                pattern_errors = pattern_checker.check_text(text, para_idx)
                all_errors.extend(pattern_errors)
        
        logger.info("开始风格检查...")
        processing_jobs[job_id]["message"] = "进行风格检查中..."
        processing_jobs[job_id]["progress"] = 60
        
        for para_idx, text in enumerate(paragraphs):
            if text.strip():
                style_errors = style_checker.check_paragraph_length(text, para_idx)
                style_errors.extend(style_checker.check_formatting(text, para_idx))
                style_errors.extend(style_checker.check_terminology(text, para_idx))
                style_errors.extend(style_checker.check_punctuation(text, para_idx))
                all_errors.extend(style_errors)
        
        if llm_checker and llm_checker.enabled:
            logger.info("开始 LLM 检查...")
            processing_jobs[job_id]["message"] = "进行 AI 深度检查中..."
            processing_jobs[job_id]["progress"] = 75
            
            for para_idx, text in enumerate(paragraphs[:5]):
                if text.strip() and len(text) > 10:
                    llm_errors = llm_checker.check_grammar(text, para_idx)
                    all_errors.extend(llm_errors)
            
            consistency_errors = llm_checker.check_consistency(paragraphs)
            all_errors.extend(consistency_errors)
        
        logger.info(f"总共发现 {len(all_errors)} 个错误")
        processing_jobs[job_id]["message"] = "应用修订中..."
        processing_jobs[job_id]["progress"] = 85
        
        revision_tracker = RevisionTracker(doc_processor)
        applied_revisions = revision_tracker.apply_error_fixes(all_errors, author_name)
        
        errors_by_severity = {}
        errors_by_type = {}
        
        for error in all_errors:
            severity = error.severity.value
            if severity not in errors_by_severity:
                errors_by_severity[severity] = 0
            errors_by_severity[severity] += 1
            
            error_type = error.error_type.value
            if error_type not in errors_by_type:
                errors_by_type[error_type] = 0
            errors_by_type[error_type] += 1
        
        logger.info("保存审校后的文档...")
        processing_jobs[job_id]["message"] = "保存文档中..."
        processing_jobs[job_id]["progress"] = 95
        
        output_file = Path(settings.OUTPUT_DIR) / f"{job_id}_reviewed.docx"
        doc_processor.save_document(str(output_file))
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        analysis = DocumentAnalysis(
            total_errors=len(all_errors),
            errors_by_type=errors_by_type,
            errors_by_severity=errors_by_severity,
            errors=all_errors[:100],
            processing_time=processing_time,
            statistics={
                "total_paragraphs": doc_stats["total_paragraphs"],
                "total_words": doc_stats["total_words"],
                "total_sentences": doc_stats["total_sentences"],
                "applied_revisions": applied_revisions,
            }
        )
        
        processing_jobs[job_id] = {
            "status": "completed",
            "progress": 100,
            "message": "处理完成！",
            "output_file": str(output_file),
            "analysis": analysis.dict(),
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "processing_time": processing_time
        }
        
        logger.info(f"任务完成 {job_id}: {processing_time:.2f}秒")
        
    except Exception as e:
        logger.error(f"处理文档失败: {e}", exc_info=True)
        processing_jobs[job_id] = {
            "status": "error",
            "message": f"处理失败: {str(e)}",
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
