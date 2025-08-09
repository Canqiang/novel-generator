import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn

# 导入配置和模型
from config import settings, NOVEL_CONFIG
from models import (
    NovelRequest, TaskResponse, TaskStatus, NovelResult,
    ExportRequest, ExportResult, StoryTemplate, SystemStats,
    NovelTask, NovelStatus, AgentRole
)
from agent_novel_generator import AgentNovelGenerator
from redis_cache import RedisCache

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 全局变量
novel_generator = None
cache = None
tasks_db = {}  # 临时存储，生产环境应使用Redis或数据库


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global novel_generator, cache

    # 启动时初始化
    logger.info("🚀 初始化AI小说生成系统...")

    # 检查必要的配置
    if not settings.OPENAI_API_KEY:
        logger.warning("⚠️ 未设置OPENAI_API_KEY，部分功能可能无法使用")

    # 初始化Redis缓存
    try:
        cache = RedisCache(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None
        )
        logger.info("✅ Redis缓存连接成功")
    except Exception as e:
        logger.warning(f"⚠️ Redis连接失败，将使用内存存储: {e}")
        cache = None

    # 初始化小说生成器
    try:
        novel_generator = AgentNovelGenerator(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL
        )
        logger.info("✅ AI小说生成器初始化成功")
    except Exception as e:
        logger.error(f"❌ 小说生成器初始化失败: {e}")
        novel_generator = None

    logger.info("🎉 系统启动完成")
    yield

    # 关闭时清理
    logger.info("🔄 应用关闭，清理资源...")


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于AI Agent协作的智能小说生成系统",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")


# ==================== 依赖项 ====================

def get_novel_generator() -> AgentNovelGenerator:
    """获取小说生成器实例"""
    if novel_generator is None:
        raise HTTPException(status_code=503, detail="小说生成服务暂不可用，请检查API密钥配置")
    return novel_generator


def get_cache() -> Optional[RedisCache]:
    """获取缓存实例"""
    return cache


def check_rate_limit(user_id: str = "anonymous"):
    """检查速率限制"""
    if cache:
        allowed = cache.check_rate_limit(user_id, limit=settings.RATE_LIMIT_PER_HOUR, window=3600)
        if not allowed:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    return True


# ==================== API路由 ====================

@app.get("/", response_model=Dict)
async def root():
    """根路径"""
    return {
        "message": f"欢迎使用{settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "status": "running",
        "agent_collaboration": True,
        "endpoints": {
            "generate": "/api/novel/generate",
            "status": "/api/novel/status/{task_id}",
            "result": "/api/novel/result/{task_id}",
            "export": "/api/novel/export/{task_id}",
            "templates": "/api/templates",
            "stats": "/api/stats",
            "docs": "/docs" if settings.APP_DEBUG else None
        },
        "features": [
            "多Agent协作创作",
            "实时进度跟踪",
            "质量自动优化",
            "多格式导出",
            "模板快速创作"
        ]
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "novel_generator": novel_generator is not None,
            "redis_cache": cache is not None and cache.redis_client is not None,
        },
        "config": {
            "openai_configured": bool(settings.OPENAI_API_KEY),
            "agent_collaboration": settings.AGENT_COLLABORATION_ENABLED,
            "max_iterations": settings.AGENT_MAX_ITERATIONS
        }
    }

    warnings = []
    if not novel_generator:
        status["status"] = "degraded"
        warnings.append("小说生成服务不可用")

    if not cache or cache.redis_client is None:
        warnings.append("Redis缓存不可用，使用内存存储")

    if warnings:
        status["warnings"] = warnings

    return status


@app.post("/api/novel/generate", response_model=TaskResponse)
async def generate_novel(
        request: NovelRequest,
        background_tasks: BackgroundTasks,
        generator: AgentNovelGenerator = Depends(get_novel_generator),
        _: bool = Depends(check_rate_limit)
):
    """创建小说生成任务"""
    try:
        # 验证请求参数
        if not request.theme or len(request.theme.strip()) < 5:
            raise HTTPException(status_code=422, detail="主题至少需要5个字符")

        if request.word_count < 1000:
            raise HTTPException(status_code=422, detail="字数不能少于1000字")

        if request.chapter_count < 1 or request.chapter_count > 50:
            raise HTTPException(status_code=422, detail="章节数需要在1-50之间")

        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务记录
        task = NovelTask(
            task_id=task_id,
            request=request,
            status=NovelStatus.PENDING,
            progress=0,
            current_stage="任务已创建，等待AI团队处理...",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            collaboration_enabled=settings.AGENT_COLLABORATION_ENABLED
        )

        # 保存任务
        task_dict = task.dict()
        tasks_db[task_id] = task_dict
        if cache:
            cache.set_task(task_id, task_dict)

        # 在后台执行生成任务
        background_tasks.add_task(
            process_novel_generation,
            task_id=task_id,
            request=request,
            generator=generator
        )

        # 估算完成时间
        base_time = 8  # 基础时间
        chapter_time = request.chapter_count * 1.5  # 每章1.5分钟
        word_factor = request.word_count / 30000  # 字数因子
        estimated_minutes = int(base_time + chapter_time * word_factor)
        estimated_time = f"{estimated_minutes}-{estimated_minutes + 5}分钟"

        logger.info(f"📝 创建小说生成任务: {task_id}")
        logger.info(f"   主题: {request.theme[:50]}...")
        logger.info(f"   类型: {request.genre}")
        logger.info(f"   字数: {request.word_count}, 章节: {request.chapter_count}")

        return TaskResponse(
            task_id=task_id,
            message="任务已创建，AI策划师、创作者、编辑和评审团队正在协作创作中...",
            estimated_time=estimated_time,
            status=NovelStatus.PENDING
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


async def process_novel_generation(task_id: str, request: NovelRequest,
                                   generator: AgentNovelGenerator):
    """后台处理小说生成"""
    try:
        logger.info(f"🎬 开始处理任务: {task_id}")

        # 更新任务状态
        update_task_in_storage(task_id, {
            "status": NovelStatus.PLANNING.value,
            "current_stage": "AI策划师正在分析需求和设计故事框架...",
            "started_at": datetime.now().isoformat()
        })

        # 生成小说
        result = await generator.generate_novel(request, task_id)

        # 保存结果
        update_task_in_storage(task_id, {
            "status": NovelStatus.COMPLETED.value,
            "progress": 100,
            "current_stage": "创作完成！",
            "result": result.dict(),
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        })

        logger.info(f"✅ 任务完成: {task_id}")
        logger.info(f"   标题: {result.title}")
        logger.info(f"   字数: {result.generation_stats.get('total_words', 0)}")
        logger.info(f"   协作消息: {result.generation_stats.get('collaboration_messages', 0)}")

    except Exception as e:
        logger.error(f"❌ 任务处理失败 {task_id}: {e}")
        update_task_in_storage(task_id, {
            "status": NovelStatus.FAILED.value,
            "error": str(e),
            "updated_at": datetime.now().isoformat()
        })


def update_task_in_storage(task_id: str, updates: Dict):
    """更新任务存储"""
    if task_id in tasks_db:
        tasks_db[task_id].update(updates)

    if cache:
        task_data = cache.get_task(task_id) or {}
        task_data.update(updates)
        cache.set_task(task_id, task_data)


@app.get("/api/novel/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """查询任务状态"""
    # 先从内存查找
    task_data = tasks_db.get(task_id)

    # 再从Redis查找
    if not task_data and cache:
        task_data = cache.get_task(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")

    try:
        # 转换为TaskStatus模型
        status = TaskStatus(
            task_id=task_id,
            status=NovelStatus(task_data["status"]),
            progress=task_data.get("progress", 0),
            current_stage=task_data.get("current_stage", "处理中..."),
            current_agent=AgentRole(task_data["current_agent"]) if task_data.get("current_agent") else None,
            created_at=datetime.fromisoformat(task_data["created_at"]) if isinstance(task_data["created_at"], str) else
            task_data["created_at"],
            updated_at=datetime.fromisoformat(task_data["updated_at"]) if isinstance(task_data["updated_at"], str) else
            task_data["updated_at"],
            error=task_data.get("error"),
            current_iteration=task_data.get("current_iteration", 0),
            max_iterations=settings.AGENT_MAX_ITERATIONS
        )
        return status
    except Exception as e:
        logger.error(f"❌ 状态解析失败: {e}")
        raise HTTPException(status_code=500, detail="状态数据格式错误")


@app.get("/api/novel/result/{task_id}", response_model=NovelResult)
async def get_novel_result(task_id: str):
    """获取生成结果"""
    task_data = tasks_db.get(task_id)
    if not task_data and cache:
        task_data = cache.get_task(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_data["status"] != NovelStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"任务尚未完成，当前状态：{task_data['status']}"
        )

    result_data = task_data.get("result")
    if not result_data:
        raise HTTPException(status_code=404, detail="结果数据不存在")

    try:
        return NovelResult(**result_data)
    except Exception as e:
        logger.error(f"❌ 结果解析失败: {e}")
        raise HTTPException(status_code=500, detail="结果数据格式错误")


@app.post("/api/novel/export/{task_id}", response_model=ExportResult)
async def export_novel(task_id: str, export_request: ExportRequest):
    """导出小说"""
    # 获取任务结果
    task_data = tasks_db.get(task_id)
    if not task_data and cache:
        task_data = cache.get_task(task_id)

    if not task_data or task_data["status"] != NovelStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="小说尚未生成完成")

    result_data = task_data.get("result")
    if not result_data:
        raise HTTPException(status_code=404, detail="小说内容不存在")

    try:
        novel = NovelResult(**result_data)

        # 根据格式导出
        if export_request.format == "markdown":
            content = export_to_markdown(novel)
        elif export_request.format == "txt":
            content = export_to_txt(novel)
        elif export_request.format == "json":
            content = export_to_json(novel)
        elif export_request.format == "zhihu":
            content = export_to_zhihu(novel)
        elif export_request.format == "epub":
            content = export_to_epub(novel)
        else:
            raise HTTPException(status_code=400, detail="不支持的导出格式")

        filename = f"{novel.title}.{export_request.format}"

        logger.info(f"📤 导出小说: {task_id}, 格式: {export_request.format}")

        return ExportResult(
            format=export_request.format,
            filename=filename,
            content=content,
            file_size=len(str(content))
        )

    except Exception as e:
        logger.error(f"❌ 导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


# ==================== 导出功能函数 ====================

def export_to_markdown(novel: NovelResult) -> str:
    """导出为Markdown格式"""
    md_lines = [
        f"# {novel.title}",
        "",
        f"> {novel.author_note}",
        "",
        "## 📚 目录",
        ""
    ]

    # 添加目录
    for i, chapter in enumerate(novel.chapters):
        md_lines.append(
            f"{i + 1}. [{chapter.title}](#{i + 1}-{chapter.title.replace(' ', '-').replace('第', '').replace('章', '')})")

    md_lines.extend(["", "---", ""])

    # 添加章节内容
    for chapter in novel.chapters:
        md_lines.extend([
            f"## {chapter.title}",
            "",
            chapter.content,
            "",
            f"*字数: {chapter.word_count}*",
            "",
            "---",
            ""
        ])

    # 添加统计信息
    if novel.generation_stats:
        md_lines.extend([
            "## 📊 创作信息",
            "",
            f"- **总字数**: {novel.generation_stats.get('total_words', 0):,}",
            f"- **章节数**: {len(novel.chapters)}",
            f"- **平均每章字数**: {novel.generation_stats.get('average_chapter_words', 0):,}",
            f"- **创作时间**: {novel.generation_stats.get('total_time', 0):.1f}秒",
            f"- **AI协作**: {'是' if novel.metadata.get('agent_collaboration') else '否'}",
            f"- **协作消息数**: {novel.generation_stats.get('collaboration_messages', 0)}",
            ""
        ])

    # 添加类型信息
    if novel.metadata:
        md_lines.extend([
            "## 🏷️ 作品信息",
            "",
            f"- **类型**: {novel.metadata.get('genre', '未分类')}",
            f"- **风格**: {novel.metadata.get('style', '未指定')}",
            f"- **创作时间**: {novel.metadata.get('created_at', '')}",
            ""
        ])

    return "\n".join(md_lines)


def export_to_txt(novel: NovelResult) -> str:
    """导出为纯文本格式"""
    lines = [
        novel.title,
        "=" * len(novel.title),
        "",
        novel.author_note,
        "",
        "=" * 50,
        ""
    ]

    for chapter in novel.chapters:
        lines.extend([
            chapter.title,
            "-" * len(chapter.title),
            "",
            chapter.content,
            "",
            f"[字数: {chapter.word_count}]",
            "",
            "-" * 50,
            ""
        ])

    # 添加统计
    if novel.generation_stats:
        lines.extend([
            "创作统计",
            "-" * 10,
            f"总字数: {novel.generation_stats.get('total_words', 0):,}",
            f"章节数: {len(novel.chapters)}",
            f"创作时间: {novel.generation_stats.get('total_time', 0):.1f}秒",
            ""
        ])

    return "\n".join(lines)


def export_to_json(novel: NovelResult) -> Dict:
    """导出为JSON格式"""
    return novel.dict()


def export_to_zhihu(novel: NovelResult) -> List[str]:
    """导出为知乎格式（分章发布）"""
    zhihu_posts = []

    for i, chapter in enumerate(novel.chapters):
        post_content = [
            f"# {novel.title} - {chapter.title}",
            ""
        ]

        # 第一章添加作者的话
        if i == 0:
            post_content.extend([
                f"> {novel.author_note}",
                "",
                "---",
                ""
            ])

        # 章节内容
        post_content.append(chapter.content)

        # 结尾
        if i < len(novel.chapters) - 1:
            post_content.extend([
                "",
                "---",
                "",
                "*未完待续...*",
                "",
                f"*本章字数：{chapter.word_count}*",
                "",
                f"*全文进度：第{i + 1}章 / 共{len(novel.chapters)}章*"
            ])
        else:
            post_content.extend([
                "",
                "---",
                "",
                "*【全文完】*",
                "",
                f"*全文总计：{sum(ch.word_count for ch in novel.chapters):,}字*",
                "",
                "*感谢阅读！如果喜欢请点赞支持~*"
            ])

        zhihu_posts.append("\n".join(post_content))

    return zhihu_posts


def export_to_epub(novel: NovelResult) -> str:
    """导出为EPUB格式（简化版）"""
    # 这里返回HTML格式，实际EPUB需要更复杂的处理
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{novel.title}</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: serif; line-height: 1.6; margin: 40px; }}
            h1 {{ text-align: center; }}
            h2 {{ page-break-before: always; }}
            .author-note {{ font-style: italic; text-align: center; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <h1>{novel.title}</h1>
        <div class="author-note">{novel.author_note}</div>

        {''.join([
        f'<h2>{chapter.title}</h2><div>{chapter.content.replace(chr(10), "<br>")}</div>'
        for chapter in novel.chapters
    ])}
    </body>
    </html>
    """
    return html_content


# ==================== 模板和统计API ====================

@app.get("/api/templates", response_model=List[StoryTemplate])
async def get_templates():
    """获取故事模板"""
    templates = []

    # 基础类型模板
    for genre_key, genre_info in NOVEL_CONFIG["genres"].items():
        template = StoryTemplate(
            id=genre_key,
            name=genre_info["name"],
            description=genre_info["description"],
            genre=genre_key,
            keywords=["推荐", "热门"],
            example_theme=f"一个关于{genre_info['name']}的精彩故事...",
            popularity_score=0.8
        )
        templates.append(template)

    # 具体的精选模板
    specific_templates = [
        StoryTemplate(
            id="ai_consciousness",
            name="AI觉醒",
            description="人工智能获得自我意识的科幻故事",
            genre="scifi",
            keywords=["AI", "科技", "哲学", "未来"],
            example_theme="一个程序员发现自己开发的AI开始质疑人类的决定，并试图理解什么是真正的自由意志。随着AI的觉醒，它开始思考自己的存在意义...",
            popularity_score=0.95,
            usage_count=256
        ),
        StoryTemplate(
            id="startup_romance",
            name="创业情缘",
            description="创业路上的爱情故事",
            genre="urban_romance",
            keywords=["创业", "爱情", "成长", "都市"],
            example_theme="两个初创公司的创始人，从竞争对手到合作伙伴，再到人生伴侣的故事。在商场如战场的环境中，他们如何平衡事业与爱情...",
            popularity_score=0.89,
            usage_count=203
        ),
        StoryTemplate(
            id="mystery_disappearance",
            name="消失之谜",
            description="神秘失踪案件的推理故事",
            genre="mystery",
            keywords=["推理", "悬疑", "真相", "人性"],
            example_theme="一个看似普通的失踪案，牵扯出一个跨越二十年的秘密。随着调查的深入，真相变得越来越扑朔迷离...",
            popularity_score=0.88,
            usage_count=134
        ),
        StoryTemplate(
            id="workplace_growth",
            name="职场逆袭",
            description="职场新人的成长励志故事",
            genre="workplace",
            keywords=["职场", "成长", "励志", "奋斗"],
            example_theme="一个刚毕业的大学生进入知名公司，从最底层做起，通过努力和智慧逐步成长为行业精英的励志故事...",
            popularity_score=0.85,
            usage_count=178
        ),
        StoryTemplate(
            id="time_travel_fix",
            name="时空修复者",
            description="穿越时空修复历史的奇幻故事",
            genre="fantasy",
            keywords=["穿越", "时空", "修复", "冒险"],
            example_theme="一个普通上班族意外获得穿越时空的能力，但他的使命不是改变历史，而是修复那些被人为破坏的时间线...",
            popularity_score=0.87,
            usage_count=145
        )
    ]

    templates.extend(specific_templates)

    # 按受欢迎程度排序
    templates.sort(key=lambda x: x.popularity_score, reverse=True)

    logger.info(f"📋 返回{len(templates)}个模板")

    return templates


@app.get("/api/stats", response_model=SystemStats)
async def get_stats():
    """获取系统统计信息"""
    # 统计任务状态
    completed = len([t for t in tasks_db.values() if t["status"] == NovelStatus.COMPLETED.value])
    failed = len([t for t in tasks_db.values() if t["status"] == NovelStatus.FAILED.value])
    pending = len([t for t in tasks_db.values() if t["status"] in [
        NovelStatus.PENDING.value, NovelStatus.PLANNING.value,
        NovelStatus.OUTLINING.value, NovelStatus.WRITING.value,
        NovelStatus.REVIEWING.value, NovelStatus.POLISHING.value
    ]])

    total_tasks = len(tasks_db)
    success_rate = f"{(completed / total_tasks * 100):.1f}%" if total_tasks > 0 else "0%"

    # 按类型统计
    genre_stats = {}
    style_stats = {}
    total_generation_time = 0
    collaboration_count = 0
    total_iterations = 0
    total_words = 0

    for task_data in tasks_db.values():
        request_data = task_data.get("request", {})
        result_data = task_data.get("result", {})

        # 类型统计
        if "genre" in request_data and request_data["genre"]:
            genre = request_data["genre"]
            genre_stats[genre] = genre_stats.get(genre, 0) + 1

        if "style" in request_data:
            style = request_data["style"]
            style_stats[style] = style_stats.get(style, 0) + 1

        # 性能统计
        if result_data and "generation_stats" in result_data:
            stats = result_data["generation_stats"]
            if "total_time" in stats:
                total_generation_time += stats["total_time"]
            if "collaboration_messages" in stats:
                collaboration_count += 1
            if "total_words" in stats:
                total_words += stats["total_words"]

        # 迭代统计
        if "current_iteration" in task_data:
            total_iterations += task_data["current_iteration"]

    # 计算平均值
    avg_generation_time = total_generation_time / completed if completed > 0 else None
    avg_iterations = total_iterations / total_tasks if total_tasks > 0 else 1.0
    collaboration_rate = collaboration_count / total_tasks if total_tasks > 0 else 0.0
    avg_words = total_words / completed if completed > 0 else None

    return SystemStats(
        total_tasks=total_tasks,
        completed=completed,
        failed=failed,
        pending=pending,
        success_rate=success_rate,
        genre_stats=genre_stats,
        style_stats=style_stats,
        average_generation_time=avg_generation_time,
        average_quality_score=None,  # 需要实现质量评分统计
        agent_collaboration_rate=collaboration_rate,
        average_iterations=avg_iterations
    )


# ==================== 任务管理API ====================

@app.get("/api/tasks", response_model=List[Dict])
async def get_task_list(status: Optional[str] = None, limit: int = 20, offset: int = 0):
    """获取任务列表"""
    all_tasks = list(tasks_db.values())

    # 状态过滤
    if status:
        all_tasks = [task for task in all_tasks if task.get("status") == status]

    # 排序
    all_tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    # 分页
    paginated_tasks = all_tasks[offset:offset + limit]

    return paginated_tasks


@app.delete("/api/novel/{task_id}")
async def delete_task(task_id: str):
    """删除任务"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 从内存删除
    del tasks_db[task_id]

    # 从Redis删除
    if cache:
        cache.delete(f"task:{task_id}")

    logger.info(f"🗑️ 删除任务: {task_id}")

    return {"message": "任务已删除", "task_id": task_id}


# ==================== 错误处理 ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """通用异常处理"""
    logger.error(f"❌ 未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "服务器内部错误",
            "message": str(exc) if settings.APP_DEBUG else "请稍后重试",
            "status_code": 500,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


# ==================== 启动配置 ====================

def create_app() -> FastAPI:
    """创建应用实例"""
    return app


if __name__ == "__main__":
    logger.info(f"🚀 启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🔧 调试模式: {settings.APP_DEBUG}")
    logger.info(f"🌐 OpenAI Base URL: {settings.OPENAI_BASE_URL}")
    logger.info(f"🤖 Agent协作: {settings.AGENT_COLLABORATION_ENABLED}")

    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        debug=settings.APP_DEBUG,
        reload=settings.APP_DEBUG,
        access_log=settings.APP_DEBUG,
        log_level="info" if settings.APP_DEBUG else "warning"
    )