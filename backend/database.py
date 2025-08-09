from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Float, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import os
from typing import Optional, List, Dict, Any
import json
from contextlib import contextmanager

from config import settings

# 数据库配置
DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0,
    echo=settings.DATABASE_ECHO
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==================== 数据模型 ====================

class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # 用户配额和权限
    daily_token_limit = Column(Integer, default=100000)
    total_tokens_used = Column(Integer, default=0)
    subscription_tier = Column(String(50), default="free")  # free, basic, pro, enterprise
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    last_active = Column(DateTime)

    # 用户设置和偏好
    preferences = Column(JSON, default=lambda: {
        "preferred_genre": None,
        "preferred_style": "知乎风格",
        "default_word_count": 30000,
        "default_chapter_count": 12,
        "quality_threshold": 0.7,
        "enable_agent_collaboration": True,
        "auto_polish": True,
        "notification_settings": {
            "email_notifications": True,
            "task_completion": True,
            "quality_alerts": False
        }
    })

    # 统计信息
    total_novels_created = Column(Integer, default=0)
    total_words_generated = Column(Integer, default=0)
    average_quality_score = Column(Float, default=0.0)

    # 关系
    novels = relationship("Novel", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("UserTemplate", back_populates="user")
    api_keys = relationship("UserAPIKey", back_populates="user")
    generation_logs = relationship("GenerationLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"


class Novel(Base):
    """小说模型"""
    __tablename__ = "novels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 基本信息
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200))
    genre = Column(String(50))
    status = Column(String(50), default="draft")  # draft, generating, completed, failed, published

    # 内容
    outline = Column(JSON)  # 大纲JSON
    chapters = Column(JSON)  # 章节内容JSON
    metadata = Column(JSON, default=lambda: {
        "total_words": 0,
        "total_chapters": 0,
        "agent_collaboration": False,
        "quality_scores": {},
        "tags": [],
        "language": "zh-CN"
    })

    # 生成参数
    generation_params = Column(JSON)  # 保存生成时的参数
    model_used = Column(String(100))
    total_tokens = Column(Integer, default=0)
    generation_cost = Column(Float, default=0.0)
    generation_time = Column(Float, default=0.0)  # 生成耗时（秒）

    # 质量指标
    quality_scores = Column(JSON, default=lambda: {
        "overall_score": 0.0,
        "content_quality": 0.0,
        "readability": 0.0,
        "creativity": 0.0,
        "coherence": 0.0
    })

    # Agent协作信息
    agent_collaboration_log = Column(JSON, default=list)
    iteration_count = Column(Integer, default=1)
    collaboration_enabled = Column(Boolean, default=True)

    # 读者统计
    reader_stats = Column(JSON, default=lambda: {
        "view_count": 0,
        "like_count": 0,
        "share_count": 0,
        "download_count": 0,
        "average_rating": 0.0,
        "rating_count": 0
    })

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)
    completed_at = Column(DateTime)

    # 发布信息
    is_public = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)
    external_urls = Column(JSON, default=lambda: {
        "zhihu_url": None,
        "other_platforms": []
    })

    # 关系
    user = relationship("User", back_populates="novels")
    chapters_list = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    generation_logs = relationship("GenerationLog", back_populates="novel")

    def __repr__(self):
        return f"<Novel(id={self.id}, title={self.title}, status={self.status})>"


class Chapter(Base):
    """章节模型"""
    __tablename__ = "chapters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"), nullable=False)

    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200))
    content = Column(Text)
    word_count = Column(Integer)

    # 生成信息
    outline = Column(JSON)  # 章节大纲
    generation_attempts = Column(Integer, default=1)
    tokens_used = Column(Integer)
    generation_time = Column(Float)  # 生成耗时

    # 版本控制
    version = Column(Integer, default=1)
    previous_versions = Column(JSON, default=list)

    # 质量评估
    quality_score = Column(Float)
    quality_details = Column(JSON, default=lambda: {
        "completeness": 0.0,
        "plot_progression": 0.0,
        "character_development": 0.0,
        "language_quality": 0.0,
        "readability": 0.0
    })

    # Agent处理记录
    agent_notes = Column(JSON, default=lambda: {
        "writer_notes": None,
        "editor_notes": None,
        "reviewer_notes": None
    })

    # 用户评价
    user_rating = Column(Float)
    user_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    novel = relationship("Novel", back_populates="chapters_list")

    def __repr__(self):
        return f"<Chapter(id={self.id}, novel_id={self.novel_id}, number={self.chapter_number})>"


class GenerationLog(Base):
    """生成日志模型"""
    __tablename__ = "generation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    # 生成阶段和状态
    stage = Column(String(50))  # outline, chapter_outline, content, polish, review
    agent_role = Column(String(50))  # planner, writer, editor, reviewer
    status = Column(String(50))  # success, failed, timeout, retry

    # 请求和响应
    request_prompt = Column(Text)
    response_content = Column(Text)
    request_parameters = Column(JSON)

    # 性能指标
    tokens_used = Column(Integer)
    response_time = Column(Float)  # 秒
    cost = Column(Float)
    model_used = Column(String(100))

    # 质量指标
    quality_score = Column(Float)
    quality_metrics = Column(JSON)

    # 错误信息
    error_message = Column(Text)
    error_code = Column(String(50))
    retry_count = Column(Integer, default=0)

    # 上下文信息
    context_data = Column(JSON)  # 保存生成时的上下文
    iteration_number = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    novel = relationship("Novel", back_populates="generation_logs")
    user = relationship("User", back_populates="generation_logs")

    def __repr__(self):
        return f"<GenerationLog(id={self.id}, stage={self.stage}, status={self.status})>"


class UserTemplate(Base):
    """用户模板模型"""
    __tablename__ = "user_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    name = Column(String(200), nullable=False)
    description = Column(Text)
    template_type = Column(String(50))  # outline, character, world, style
    category = Column(String(50))  # 模板分类

    content = Column(JSON)
    example_usage = Column(Text)

    # 使用统计
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    average_quality = Column(Float, default=0.0)

    # 发布设置
    is_public = Column(Boolean, default=False)
    is_featured = Column(Boolean, default=False)

    # 标签和搜索
    tags = Column(JSON, default=list)
    keywords = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="templates")

    def __repr__(self):
        return f"<UserTemplate(id={self.id}, name={self.name}, type={self.template_type})>"


class UserAPIKey(Base):
    """用户API密钥模型（支持自带密钥）"""
    __tablename__ = "user_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    provider = Column(String(50))  # openai, anthropic, qwen, moonshot, etc.
    api_key_encrypted = Column(String(500))  # 加密存储
    api_key_hash = Column(String(100))  # 用于验证的哈希
    is_active = Column(Boolean, default=True)

    # 配置信息
    base_url = Column(String(500))  # 自定义API端点
    model_preferences = Column(JSON, default=lambda: {
        "preferred_model": None,
        "max_tokens": 2000,
        "temperature": 0.8
    })

    # 使用统计
    total_tokens_used = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    last_used = Column(DateTime)

    # 限制设置
    daily_limit = Column(Integer, default=100000)  # 每日Token限制
    monthly_budget = Column(Float, default=0.0)  # 月度预算限制

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, provider={self.provider}, active={self.is_active})>"


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON)
    description = Column(Text)
    category = Column(String(50))  # system, user, generation, etc.
    is_public = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig(key={self.key}, category={self.category})>"


class TaskQueue(Base):
    """任务队列模型"""
    __tablename__ = "task_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(String(100), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    task_type = Column(String(50))  # novel_generation, chapter_polish, etc.
    priority = Column(Integer, default=0)  # 优先级，数字越大优先级越高
    status = Column(String(50), default="pending")  # pending, processing, completed, failed

    # 任务数据
    task_data = Column(JSON)
    result_data = Column(JSON)
    error_message = Column(Text)

    # 处理信息
    worker_id = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TaskQueue(task_id={self.task_id}, status={self.status})>"


# ==================== 数据库操作类 ====================

class DatabaseManager:
    """数据库管理器"""

    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    @contextmanager
    def get_session(self):
        """获取数据库会话"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """删除所有表"""
        Base.metadata.drop_all(bind=self.engine)

    def init_system_data(self):
        """初始化系统数据"""
        with self.get_session() as session:
            # 检查是否已初始化
            existing_config = session.query(SystemConfig).filter_by(key="system_initialized").first()
            if existing_config:
                return

            # 创建默认系统配置
            default_configs = [
                {
                    "key": "system_initialized",
                    "value": {"initialized": True, "version": "1.0.0"},
                    "description": "系统初始化标记",
                    "category": "system"
                },
                {
                    "key": "default_generation_params",
                    "value": {
                        "max_tokens": 2000,
                        "temperature": 0.8,
                        "max_iterations": 3,
                        "quality_threshold": 0.7
                    },
                    "description": "默认生成参数",
                    "category": "generation"
                },
                {
                    "key": "subscription_tiers",
                    "value": {
                        "free": {"daily_tokens": 10000, "monthly_novels": 2},
                        "basic": {"daily_tokens": 50000, "monthly_novels": 10},
                        "pro": {"daily_tokens": 200000, "monthly_novels": 50},
                        "enterprise": {"daily_tokens": 1000000, "monthly_novels": 200}
                    },
                    "description": "订阅等级配置",
                    "category": "user",
                    "is_public": True
                }
            ]

            for config_data in default_configs:
                config = SystemConfig(**config_data)
                session.add(config)

            session.commit()


# ==================== 数据库操作函数 ====================

def get_db():
    """获取数据库会话（依赖注入用）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """初始化数据库"""
    print("🏗️ 创建数据库表...")

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    # 初始化系统数据
    db_manager = DatabaseManager()
    db_manager.init_system_data()

    print("✅ 数据库初始化完成")


def check_database_connection():
    """检查数据库连接"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


# ==================== 实用工具函数 ====================

def create_sample_user():
    """创建示例用户"""
    with SessionLocal() as session:
        # 检查是否已存在示例用户
        existing_user = session.query(User).filter_by(email="demo@example.com").first()
        if existing_user:
            print("✅ 示例用户已存在")
            return existing_user

        # 创建示例用户
        import bcrypt
        password_hash = bcrypt.hashpw("demo123".encode('utf-8'), bcrypt.gensalt())

        user = User(
            email="demo@example.com",
            username="demo_user",
            password_hash=password_hash.decode('utf-8'),
            is_verified=True,
            subscription_tier="pro"
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        print(f"✅ 创建示例用户: {user.username}")
        return user


def cleanup_old_data(days: int = 30):
    """清理旧数据"""
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    with SessionLocal() as session:
        # 清理旧的生成日志
        old_logs = session.query(GenerationLog).filter(
            GenerationLog.created_at < cutoff_date
        ).count()

        session.query(GenerationLog).filter(
            GenerationLog.created_at < cutoff_date
        ).delete()

        # 清理失败的任务
        failed_tasks = session.query(TaskQueue).filter(
            TaskQueue.status == "failed",
            TaskQueue.created_at < cutoff_date
        ).count()

        session.query(TaskQueue).filter(
            TaskQueue.status == "failed",
            TaskQueue.created_at < cutoff_date
        ).delete()

        session.commit()

        print(f"🧹 清理完成：删除了{old_logs}条日志，{failed_tasks}个失败任务")


def get_database_stats():
    """获取数据库统计信息"""
    with SessionLocal() as session:
        stats = {
            "users": session.query(User).count(),
            "novels": session.query(Novel).count(),
            "chapters": session.query(Chapter).count(),
            "generation_logs": session.query(GenerationLog).count(),
            "templates": session.query(UserTemplate).count(),
            "pending_tasks": session.query(TaskQueue).filter_by(status="pending").count()
        }

        # 统计完成的小说
        completed_novels = session.query(Novel).filter_by(status="completed").count()
        stats["completed_novels"] = completed_novels

        # 统计总字数
        total_words = session.query(Novel).with_entities(
            Novel.metadata
        ).all()

        word_count = 0
        for novel in total_words:
            if novel.metadata and "total_words" in novel.metadata:
                word_count += novel.metadata["total_words"]

        stats["total_words"] = word_count

        return stats


# ==================== 主函数 ====================

if __name__ == "__main__":
    print("🚀 数据库模块测试")

    # 检查连接
    if check_database_connection():
        print("✅ 数据库连接正常")

        # 初始化数据库
        init_database()

        # 创建示例数据
        create_sample_user()

        # 显示统计信息
        stats = get_database_stats()
        print("📊 数据库统计:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

    else:
        print("❌ 数据库连接失败")
        exit(1)