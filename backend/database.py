from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Float, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
import os
from typing import Optional

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/novel_generator")

engine = create_engine(DATABASE_URL, pool_size=20, max_overflow=0)
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

    # 用户配额
    daily_token_limit = Column(Integer, default=100000)
    total_tokens_used = Column(Integer, default=0)
    subscription_tier = Column(String(50), default="free")  # free, basic, pro, enterprise

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # 用户设置
    preferences = Column(JSON, default={})

    # 关系
    novels = relationship("Novel", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("UserTemplate", back_populates="user")
    api_keys = relationship("UserAPIKey", back_populates="user")


class Novel(Base):
    """小说模型"""
    __tablename__ = "novels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 基本信息
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200))
    genre = Column(String(50))
    status = Column(String(50), default="draft")  # draft, generating, completed, published

    # 内容
    outline = Column(JSON)  # 大纲JSON
    chapters = Column(JSON)  # 章节内容JSON
    metadata = Column(JSON)  # 元数据（字数、token等）

    # 生成参数
    generation_params = Column(JSON)  # 保存生成时的参数
    model_used = Column(String(100))
    total_tokens = Column(Integer, default=0)
    generation_cost = Column(Float, default=0.0)

    # 质量指标
    quality_scores = Column(JSON)  # 各维度质量评分
    reader_stats = Column(JSON)  # 阅读统计

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime)

    # 发布信息
    is_public = Column(Boolean, default=False)
    zhihu_url = Column(String(500))
    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)

    # 关系
    user = relationship("User", back_populates="novels")
    chapters_list = relationship("Chapter", back_populates="novel", cascade="all, delete-orphan")
    generation_logs = relationship("GenerationLog", back_populates="novel")


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

    # 版本控制
    version = Column(Integer, default=1)
    previous_versions = Column(JSON, default=[])

    # 质量
    quality_score = Column(Float)
    user_rating = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    novel = relationship("Novel", back_populates="chapters_list")


class GenerationLog(Base):
    """生成日志模型"""
    __tablename__ = "generation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    novel_id = Column(UUID(as_uuid=True), ForeignKey("novels.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    stage = Column(String(50))  # outline, chapter_expand, content, polish
    status = Column(String(50))  # success, failed, timeout

    # 请求响应
    request_prompt = Column(Text)
    response_content = Column(Text)

    # 性能指标
    tokens_used = Column(Integer)
    response_time = Column(Float)  # 秒
    cost = Column(Float)

    # 错误信息
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    novel = relationship("Novel", back_populates="generation_logs")


class UserTemplate(Base):
    """用户模板模型"""
    __tablename__ = "user_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    name = Column(String(200), nullable=False)
    description = Column(Text)
    template_type = Column(String(50))  # outline, character, world, style

    content = Column(JSON)
    usage_count = Column(Integer, default=0)
    is_public = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="templates")


class UserAPIKey(Base):
    """用户API密钥模型（支持自带密钥）"""
    __tablename__ = "user_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    provider = Column(String(50))  # openai, anthropic, qwen, etc.
    api_key_encrypted = Column(String(500))  # 加密存储
    is_active = Column(Boolean, default=True)

    # 使用统计
    total_tokens_used = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    last_used = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="api_keys")
