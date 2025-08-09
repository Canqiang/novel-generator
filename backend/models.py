from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, validator


class NovelGenre(str, Enum):
    """小说类型枚举"""
    URBAN_ROMANCE = "urban_romance"
    MYSTERY = "mystery"
    SCIFI = "scifi"
    WORKPLACE = "workplace"
    FANTASY = "fantasy"


class WritingStyle(str, Enum):
    """写作风格枚举"""
    ZHIHU = "知乎风格"
    HUMOROUS = "轻松幽默"
    LITERARY = "文艺细腻"
    SUSPENSEFUL = "紧张刺激"


class NovelStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    PLANNING = "planning"
    OUTLINING = "outlining"
    WRITING = "writing"
    REVIEWING = "reviewing"
    POLISHING = "polishing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRole(str, Enum):
    """Agent角色枚举"""
    PLANNER = "planner"
    WRITER = "writer"
    EDITOR = "editor"
    REVIEWER = "reviewer"


# ==================== 请求模型 ====================

class NovelRequest(BaseModel):
    """小说生成请求"""
    theme: str = Field(..., min_length=5, max_length=500, description="故事主题")
    genre: Optional[NovelGenre] = Field(None, description="小说类型")
    style: WritingStyle = Field(WritingStyle.ZHIHU, description="写作风格")
    word_count: int = Field(30000, ge=5000, le=100000, description="目标字数")
    chapter_count: int = Field(12, ge=3, le=30, description="章节数量")

    # 高级选项
    target_audience: Optional[str] = Field("知乎用户", description="目标读者")
    special_requirements: Optional[str] = Field(None, description="特殊要求")
    reference_works: Optional[List[str]] = Field(None, description="参考作品")

    @validator('theme')
    def validate_theme(cls, v):
        if not v or v.strip() == '':
            raise ValueError('主题不能为空')
        return v.strip()

    @validator('word_count')
    def validate_word_count(cls, v, values):
        chapter_count = values.get('chapter_count', 12)
        min_per_chapter = v // chapter_count
        if min_per_chapter < 200:
            raise ValueError('每章字数不能少于200字')
        return v


class AgentMessage(BaseModel):
    """Agent消息模型"""
    role: AgentRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    """Agent响应模型"""
    agent_role: AgentRole
    content: str
    quality_score: Optional[float] = None
    suggestions: Optional[List[str]] = None
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ==================== 响应模型 ====================

class TaskResponse(BaseModel):
    """任务创建响应"""
    task_id: str
    message: str
    estimated_time: str
    status: NovelStatus


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: NovelStatus
    progress: int = Field(ge=0, le=100)
    current_stage: str
    current_agent: Optional[AgentRole] = None
    created_at: datetime
    updated_at: datetime
    estimated_completion: Optional[datetime] = None
    error: Optional[str] = None

    # Agent协作信息
    agent_history: List[AgentMessage] = Field(default_factory=list)
    current_iteration: int = 0
    max_iterations: int = 3


class ChapterOutline(BaseModel):
    """章节大纲"""
    chapter_num: int
    title: str
    summary: str
    key_events: List[str]
    characters_involved: List[str]
    mood: str
    target_word_count: int

    # Agent评审信息
    planner_notes: Optional[str] = None
    reviewer_score: Optional[float] = None


class NovelOutline(BaseModel):
    """小说大纲"""
    title: str
    subtitle: Optional[str] = None
    author_note: str
    one_line_pitch: str
    genre: str
    theme: str
    tone: str

    # 人物设定
    characters: Dict[str, Any]

    # 世界观设定
    world_setting: Dict[str, Any]

    # 情节结构
    plot_structure: Dict[str, Any]
    plot_points: List[str]

    # 章节大纲
    chapter_outlines: List[ChapterOutline]

    # 创作指导
    themes_to_explore: List[str]
    key_symbols: List[str]
    target_readers: str

    # Agent协作信息
    creation_notes: Dict[AgentRole, str] = Field(default_factory=dict)
    quality_metrics: Dict[str, float] = Field(default_factory=dict)


class Chapter(BaseModel):
    """章节内容"""
    chapter_num: int
    title: str
    content: str
    word_count: int

    # 质量指标
    readability_score: Optional[float] = None
    engagement_score: Optional[float] = None
    coherence_score: Optional[float] = None

    # Agent处理信息
    writer_version: int = 1
    editor_notes: Optional[str] = None
    reviewer_feedback: Optional[str] = None
    revisions: List[Dict[str, Any]] = Field(default_factory=list)


class NovelResult(BaseModel):
    """小说生成结果"""
    title: str
    author_note: str
    outline: NovelOutline
    chapters: List[Chapter]

    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # 生成统计
    generation_stats: Dict[str, Any] = Field(default_factory=dict)

    # Agent协作历史
    collaboration_log: List[AgentMessage] = Field(default_factory=list)
    final_quality_report: Optional[Dict[str, Any]] = None


# ==================== 导出模型 ====================

class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(..., regex='^(markdown|txt|json|zhihu|epub)$')
    include_metadata: bool = True
    custom_formatting: Optional[Dict[str, Any]] = None


class ExportResult(BaseModel):
    """导出结果"""
    format: str
    filename: str
    content: Any  # 可能是字符串或字节数据
    file_size: int
    download_url: Optional[str] = None


# ==================== 模板模型 ====================

class StoryTemplate(BaseModel):
    """故事模板"""
    id: str
    name: str
    description: str
    genre: NovelGenre
    keywords: List[str]
    example_theme: str
    example_outline: Optional[Dict[str, Any]] = None
    popularity_score: float = 0.0
    usage_count: int = 0


class UserPreferences(BaseModel):
    """用户偏好设置"""
    preferred_genre: Optional[NovelGenre] = None
    preferred_style: WritingStyle = WritingStyle.ZHIHU
    default_word_count: int = 30000
    default_chapter_count: int = 12
    quality_threshold: float = 0.7
    enable_agent_collaboration: bool = True
    auto_polish: bool = True


# ==================== 统计模型 ====================

class SystemStats(BaseModel):
    """系统统计"""
    total_tasks: int
    completed: int
    failed: int
    pending: int
    success_rate: str

    # 按类型统计
    genre_stats: Dict[str, int] = Field(default_factory=dict)
    style_stats: Dict[str, int] = Field(default_factory=dict)

    # 性能统计
    average_generation_time: Optional[float] = None
    average_quality_score: Optional[float] = None

    # Agent统计
    agent_collaboration_rate: float = 0.0
    average_iterations: float = 1.0


# ==================== 任务存储模型 ====================

class NovelTask(BaseModel):
    """内部任务模型"""
    task_id: str
    user_id: Optional[str] = None
    request: NovelRequest
    status: NovelStatus
    progress: int = 0
    current_stage: str = "初始化"
    current_agent: Optional[AgentRole] = None

    # 时间信息
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 结果和错误
    result: Optional[NovelResult] = None
    error: Optional[str] = None

    # Agent协作
    agent_messages: List[AgentMessage] = Field(default_factory=list)
    current_iteration: int = 0
    collaboration_enabled: bool = True

    # 性能指标
    tokens_used: int = 0
    api_calls: int = 0
    generation_cost: float = 0.0

    class Config:
        use_enum_values = True