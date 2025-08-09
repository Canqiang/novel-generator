# main.py - 主应用入口
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum

# 导入其他模块
from novel_generator import NovelGenerator
from prompt_templates import PromptTemplates
from database import Database
from redis_cache import RedisCache

app = FastAPI(title="AI小说生成系统")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== 数据模型 ==============

class NovelGenre(str, Enum):
    URBAN_ROMANCE = "urban_romance"
    MYSTERY = "mystery"
    SCIFI = "scifi"
    WORKPLACE = "workplace"
    FANTASY = "fantasy"


class NovelRequest(BaseModel):
    theme: str  # 用户输入的主题
    genre: Optional[NovelGenre] = None
    style: Optional[str] = "知乎风格"
    word_count: Optional[int] = 30000
    chapter_count: Optional[int] = 12


class NovelStatus(str, Enum):
    PENDING = "pending"
    OUTLINING = "outlining"
    WRITING = "writing"
    POLISHING = "polishing"
    COMPLETED = "completed"
    FAILED = "failed"


class NovelTask(BaseModel):
    task_id: str
    status: NovelStatus
    progress: int  # 0-100
    current_stage: str
    created_at: datetime
    updated_at: datetime
    result: Optional[Dict] = None
    error: Optional[str] = None

# 任务存储（实际应用中应使用Redis）
tasks_db = {}


@app.post("/api/novel/generate", response_model=Dict)
async def generate_novel(request: NovelRequest, background_tasks: BackgroundTasks):
    """创建小说生成任务"""
    task_id = str(uuid.uuid4())

    # 创建任务记录
    task = NovelTask(
        task_id=task_id,
        status=NovelStatus.PENDING,
        progress=0,
        current_stage="初始化",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    tasks_db[task_id] = task.dict()

    # 在后台执行生成任务
    background_tasks.add_task(
        process_novel_generation,
        task_id=task_id,
        request=request
    )

    return {
        "task_id": task_id,
        "message": "任务已创建，正在生成中...",
        "estimated_time": "10-15分钟"
    }


async def process_novel_generation(task_id: str, request: NovelRequest):
    """后台处理小说生成"""
    generator = NovelGenerator(api_key="your-openai-api-key")

    try:
        result = await generator.generate_novel(request, task_id)
        tasks_db[task_id]["status"] = NovelStatus.COMPLETED
        tasks_db[task_id]["result"] = result
        tasks_db[task_id]["updated_at"] = datetime.now()
    except Exception as e:
        tasks_db[task_id]["status"] = NovelStatus.FAILED
        tasks_db[task_id]["error"] = str(e)
        tasks_db[task_id]["updated_at"] = datetime.now()


@app.get("/api/novel/status/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    return tasks_db[task_id]


@app.get("/api/novel/result/{task_id}")
async def get_novel_result(task_id: str):
    """获取生成结果"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks_db[task_id]

    if task["status"] != NovelStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"任务状态：{task['status']}")

    return task["result"]


@app.post("/api/novel/export/{task_id}")
async def export_novel(task_id: str, format: str = "markdown"):
    """导出小说"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks_db[task_id]
    if task["status"] != NovelStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="小说尚未生成完成")

    novel = task["result"]

    if format == "markdown":
        content = export_to_markdown(novel)
    elif format == "zhihu":
        content = export_to_zhihu(novel)
    else:
        content = export_to_json(novel)

    return {
        "format": format,
        "content": content,
        "filename": f"{novel['title']}.{format}"
    }


def export_to_markdown(novel: Dict) -> str:
    """导出为Markdown格式"""
    md = f"# {novel['title']}\n\n"
    md += f"> {novel['author_note']}\n\n"

    for chapter in novel["chapters"]:
        md += f"## {chapter['title']}\n\n"
        md += chapter["content"]
        md += "\n\n---\n\n"

    return md


def export_to_zhihu(novel: Dict) -> List[str]:
    """导出为知乎格式（分章）"""
    chapters = []

    for i, chapter in enumerate(novel["chapters"]):
        zhihu_content = f"# {novel['title']} - {chapter['title']}\n\n"

        if i == 0:
            zhihu_content += f"> {novel['author_note']}\n\n"

        zhihu_content += chapter["content"]
        zhihu_content += f"\n\n---\n\n*未完待续...*"

        chapters.append(zhihu_content)

    return chapters


@app.get("/api/templates")
async def get_templates():
    """获取可用的故事模板"""
    templates = [
        {
            "id": "urban_love",
            "name": "都市爱情",
            "description": "现代都市背景的情感故事",
            "keywords": ["爱情", "都市", "职场", "成长"],
            "example": "一个程序员与设计师的相遇..."
        },
        {
            "id": "ai_scifi",
            "name": "AI科幻",
            "description": "关于人工智能的科幻故事",
            "keywords": ["AI", "未来", "科技", "伦理"],
            "example": "当AI开始理解人类的情感..."
        },
        {
            "id": "mystery_suspense",
            "name": "悬疑推理",
            "description": "充满谜团和反转的推理故事",
            "keywords": ["推理", "悬疑", "反转", "真相"],
            "example": "一封匿名信引发的连环谜案..."
        }
    ]
    return templates


@app.get("/api/stats")
async def get_stats():
    """获取系统统计信息"""
    completed = len([t for t in tasks_db.values() if t["status"] == NovelStatus.COMPLETED])
    failed = len([t for t in tasks_db.values() if t["status"] == NovelStatus.FAILED])
    pending = len([t for t in tasks_db.values() if
                   t["status"] in [NovelStatus.PENDING, NovelStatus.OUTLINING, NovelStatus.WRITING,
                                   NovelStatus.POLISHING]])

    return {
        "total_tasks": len(tasks_db),
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "success_rate": f"{(completed / len(tasks_db) * 100):.1f}%" if tasks_db else "0%"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)