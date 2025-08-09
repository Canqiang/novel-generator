from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from datetime import datetime, timedelta
import bcrypt
import json
import uuid

from database import (
    User, Novel, Chapter, GenerationLog, UserTemplate,
    UserAPIKey, SystemConfig, TaskQueue
)
from models import NovelRequest, NovelResult


class DatabaseOperations:
    """数据库操作封装类"""

    def __init__(self, db: Session):
        self.db = db

    # ==================== 用户操作 ====================

    def create_user(self, email: str, username: str, password: str, **kwargs) -> User:
        """创建用户"""
        # 检查用户是否已存在
        existing_user = self.get_user_by_email(email)
        if existing_user:
            raise ValueError(f"邮箱 {email} 已被使用")

        existing_username = self.get_user_by_username(username)
        if existing_username:
            raise ValueError(f"用户名 {username} 已被使用")

        # 密码加密
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user = User(
            email=email,
            username=username,
            password_hash=password_hash.decode('utf-8'),
            **kwargs
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        return self.db.query(User).filter(User.username == username).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()

    def verify_password(self, user: User, password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8')
        )

    def update_user_password(self, user_id: str, new_password: str) -> bool:
        """更新用户密码"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        user.password_hash = password_hash.decode('utf-8')
        user.updated_at = datetime.utcnow()

        self.db.commit()
        return True

    def update_user_tokens(self, user_id: str, tokens_used: int) -> None:
        """更新用户Token使用量"""
        user = self.get_user_by_id(user_id)
        if user:
            user.total_tokens_used += tokens_used
            user.updated_at = datetime.utcnow()
            self.db.commit()

    def update_user_preferences(self, user_id: str, preferences: Dict) -> bool:
        """更新用户偏好设置"""
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # 合并偏好设置
        current_prefs = user.preferences or {}
        current_prefs.update(preferences)
        user.preferences = current_prefs
        user.updated_at = datetime.utcnow()

        self.db.commit()
        return True

    def update_user_last_login(self, user_id: str) -> None:
        """更新用户最后登录时间"""
        user = self.get_user_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
            user.last_active = datetime.utcnow()
            self.db.commit()

    def get_user_statistics(self, user_id: str) -> Dict:
        """获取用户统计信息"""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}

        # 统计小说数量
        novel_stats = self.db.query(
            func.count(Novel.id).label('total'),
            func.count(func.nullif(Novel.status, 'completed')).label('completed'),
            func.sum(Novel.total_tokens).label('total_tokens')
        ).filter(Novel.user_id == user_id).first()

        # 统计生成日志
        log_stats = self.db.query(
            func.count(GenerationLog.id).label('total_generations'),
            func.sum(GenerationLog.tokens_used).label('tokens_used'),
            func.sum(GenerationLog.cost).label('total_cost')
        ).filter(GenerationLog.user_id == user_id).first()

        return {
            "user_info": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "subscription_tier": user.subscription_tier,
                "created_at": user.created_at,
                "last_login": user.last_login
            },
            "novel_stats": {
                "total_novels": novel_stats.total or 0,
                "completed_novels": novel_stats.completed or 0,
                "total_words": user.total_words_generated or 0,
                "average_quality": user.average_quality_score or 0.0
            },
            "usage_stats": {
                "total_tokens": user.total_tokens_used or 0,
                "total_generations": log_stats.total_generations or 0,
                "total_cost": log_stats.total_cost or 0.0
            }
        }

    # ==================== 小说操作 ====================

    def create_novel(self, user_id: str, title: str, **kwargs) -> Novel:
        """创建小说"""
        novel = Novel(
            user_id=user_id,
            title=title,
            **kwargs
        )

        self.db.add(novel)
        self.db.commit()
        self.db.refresh(novel)
        return novel

    def get_novel_by_id(self, novel_id: str) -> Optional[Novel]:
        """通过ID获取小说"""
        return self.db.query(Novel).filter(Novel.id == novel_id).first()

    def get_user_novels(self, user_id: str, status: str = None,
                        limit: int = 20, offset: int = 0,
                        order_by: str = "created_at", ascending: bool = False) -> List[Novel]:
        """获取用户小说列表"""
        query = self.db.query(Novel).filter(Novel.user_id == user_id)

        if status:
            query = query.filter(Novel.status == status)

        # 排序
        order_column = getattr(Novel, order_by, Novel.created_at)
        if ascending:
            query = query.order_by(asc(order_column))
        else:
            query = query.order_by(desc(order_column))

        return query.limit(limit).offset(offset).all()

    def search_novels(self, user_id: str = None, query: str = None,
                      genre: str = None, status: str = None,
                      is_public: bool = None, limit: int = 20, offset: int = 0) -> List[Novel]:
        """搜索小说"""
        db_query = self.db.query(Novel)

        if user_id:
            db_query = db_query.filter(Novel.user_id == user_id)

        if is_public is not None:
            db_query = db_query.filter(Novel.is_public == is_public)

        if status:
            db_query = db_query.filter(Novel.status == status)

        if genre:
            db_query = db_query.filter(Novel.genre == genre)

        if query:
            # 搜索标题和描述
            search_filter = or_(
                Novel.title.contains(query),
                Novel.subtitle.contains(query)
            )
            db_query = db_query.filter(search_filter)

        return db_query.order_by(desc(Novel.created_at)).limit(limit).offset(offset).all()

    def update_novel_status(self, novel_id: str, status: str, **kwargs) -> bool:
        """更新小说状态"""
        novel = self.get_novel_by_id(novel_id)
        if not novel:
            return False

        novel.status = status
        novel.updated_at = datetime.utcnow()

        # 如果完成，记录完成时间
        if status == "completed":
            novel.completed_at = datetime.utcnow()

        # 更新其他字段
        for key, value in kwargs.items():
            if hasattr(novel, key):
                setattr(novel, key, value)

        self.db.commit()
        return True

    def save_novel_content(self, novel_id: str, outline: Dict = None,
                           chapters: List = None, metadata: Dict = None) -> bool:
        """保存小说内容"""
        novel = self.get_novel_by_id(novel_id)
        if not novel:
            return False

        if outline:
            novel.outline = outline

        if chapters:
            novel.chapters = chapters
            # 更新元数据
            total_words = sum(ch.get('word_count', 0) for ch in chapters)
            if not novel.metadata:
                novel.metadata = {}
            novel.metadata['total_words'] = total_words
            novel.metadata['total_chapters'] = len(chapters)

        if metadata:
            if not novel.metadata:
                novel.metadata = {}
            novel.metadata.update(metadata)

        novel.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def delete_novel(self, novel_id: str, user_id: str = None) -> bool:
        """删除小说"""
        query = self.db.query(Novel).filter(Novel.id == novel_id)
        if user_id:
            query = query.filter(Novel.user_id == user_id)

        novel = query.first()
        if not novel:
            return False

        self.db.delete(novel)
        self.db.commit()
        return True

    def update_novel_quality_scores(self, novel_id: str, quality_scores: Dict) -> bool:
        """更新小说质量评分"""
        novel = self.get_novel_by_id(novel_id)
        if not novel:
            return False

        novel.quality_scores = quality_scores
        novel.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def increment_novel_views(self, novel_id: str) -> bool:
        """增加小说浏览量"""
        novel = self.get_novel_by_id(novel_id)
        if not novel:
            return False

        if not novel.reader_stats:
            novel.reader_stats = {"view_count": 0}

        novel.reader_stats["view_count"] = novel.reader_stats.get("view_count", 0) + 1
        self.db.commit()
        return True

    # ==================== 章节操作 ====================

    def create_chapter(self, novel_id: str, chapter_number: int, **kwargs) -> Chapter:
        """创建章节"""
        chapter = Chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            **kwargs
        )

        self.db.add(chapter)
        self.db.commit()
        self.db.refresh(chapter)
        return chapter

    def get_chapter_by_id(self, chapter_id: str) -> Optional[Chapter]:
        """获取章节"""
        return self.db.query(Chapter).filter(Chapter.id == chapter_id).first()

    def get_novel_chapters(self, novel_id: str, order_by_number: bool = True) -> List[Chapter]:
        """获取小说的所有章节"""
        query = self.db.query(Chapter).filter(Chapter.novel_id == novel_id)

        if order_by_number:
            query = query.order_by(Chapter.chapter_number)

        return query.all()

    def update_chapter_content(self, chapter_id: str, content: str,
                               word_count: int = None, **kwargs) -> bool:
        """更新章节内容"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return False

        # 保存旧版本
        if chapter.content and chapter.content != content:
            old_version = {
                'version': chapter.version,
                'content': chapter.content,
                'updated_at': chapter.updated_at.isoformat(),
                'word_count': chapter.word_count
            }

            if not chapter.previous_versions:
                chapter.previous_versions = []
            chapter.previous_versions.append(old_version)

        chapter.content = content
        chapter.word_count = word_count or len(content.split())
        chapter.version += 1
        chapter.updated_at = datetime.utcnow()

        # 更新其他字段
        for key, value in kwargs.items():
            if hasattr(chapter, key):
                setattr(chapter, key, value)

        self.db.commit()
        return True

    def delete_chapter(self, chapter_id: str) -> bool:
        """删除章节"""
        chapter = self.get_chapter_by_id(chapter_id)
        if not chapter:
            return False

        self.db.delete(chapter)
        self.db.commit()
        return True

    # ==================== 日志操作 ====================

    def log_generation(self, novel_id: str, user_id: str, stage: str,
                       status: str, **kwargs) -> GenerationLog:
        """记录生成日志"""
        log = GenerationLog(
            novel_id=novel_id,
            user_id=user_id,
            stage=stage,
            status=status,
            **kwargs
        )

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_generation_logs(self, novel_id: str = None, user_id: str = None,
                            stage: str = None, status: str = None,
                            limit: int = 100, offset: int = 0) -> List[GenerationLog]:
        """获取生成日志"""
        query = self.db.query(GenerationLog)

        if novel_id:
            query = query.filter(GenerationLog.novel_id == novel_id)

        if user_id:
            query = query.filter(GenerationLog.user_id == user_id)

        if stage:
            query = query.filter(GenerationLog.stage == stage)

        if status:
            query = query.filter(GenerationLog.status == status)

        return query.order_by(desc(GenerationLog.created_at)).limit(limit).offset(offset).all()

    def get_generation_stats(self, user_id: str, days: int = 30) -> Dict:
        """获取生成统计"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(GenerationLog).filter(
            GenerationLog.user_id == user_id,
            GenerationLog.created_at >= cutoff
        ).all()

        total_tokens = sum(log.tokens_used or 0 for log in logs)
        total_cost = sum(log.cost or 0 for log in logs)
        success_count = sum(1 for log in logs if log.status == 'success')
        failed_count = sum(1 for log in logs if log.status == 'failed')

        # 按阶段统计
        stage_stats = {}
        for log in logs:
            stage = log.stage
            if stage not in stage_stats:
                stage_stats[stage] = {"total": 0, "success": 0, "failed": 0}

            stage_stats[stage]["total"] += 1
            if log.status == "success":
                stage_stats[stage]["success"] += 1
            elif log.status == "failed":
                stage_stats[stage]["failed"] += 1

        return {
            'period_days': days,
            'total_generations': len(logs),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': success_count / len(logs) if logs else 0,
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'average_tokens': total_tokens / len(logs) if logs else 0,
            'stage_stats': stage_stats
        }

    # ==================== 模板操作 ====================

    def create_template(self, user_id: str, name: str, template_type: str,
                        content: Dict, **kwargs) -> UserTemplate:
        """创建用户模板"""
        template = UserTemplate(
            user_id=user_id,
            name=name,
            template_type=template_type,
            content=content,
            **kwargs
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_template_by_id(self, template_id: str) -> Optional[UserTemplate]:
        """获取模板"""
        return self.db.query(UserTemplate).filter(UserTemplate.id == template_id).first()

    def get_user_templates(self, user_id: str, template_type: str = None,
                           limit: int = 20, offset: int = 0) -> List[UserTemplate]:
        """获取用户模板"""
        query = self.db.query(UserTemplate).filter(UserTemplate.user_id == user_id)

        if template_type:
            query = query.filter(UserTemplate.template_type == template_type)

        return query.order_by(desc(UserTemplate.usage_count)).limit(limit).offset(offset).all()

    def get_public_templates(self, template_type: str = None,
                             category: str = None, limit: int = 20, offset: int = 0) -> List[UserTemplate]:
        """获取公开模板"""
        query = self.db.query(UserTemplate).filter(UserTemplate.is_public == True)

        if template_type:
            query = query.filter(UserTemplate.template_type == template_type)

        if category:
            query = query.filter(UserTemplate.category == category)

        return query.order_by(desc(UserTemplate.usage_count)).limit(limit).offset(offset).all()

    def update_template_usage(self, template_id: str) -> bool:
        """更新模板使用次数"""
        template = self.get_template_by_id(template_id)
        if not template:
            return False

        template.usage_count += 1
        template.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    def delete_template(self, template_id: str, user_id: str = None) -> bool:
        """删除模板"""
        query = self.db.query(UserTemplate).filter(UserTemplate.id == template_id)
        if user_id:
            query = query.filter(UserTemplate.user_id == user_id)

        template = query.first()
        if not template:
            return False

        self.db.delete(template)
        self.db.commit()
        return True

    # ==================== API密钥操作 ====================

    def create_api_key(self, user_id: str, provider: str,
                       api_key_encrypted: str, **kwargs) -> UserAPIKey:
        """创建API密钥"""
        api_key = UserAPIKey(
            user_id=user_id,
            provider=provider,
            api_key_encrypted=api_key_encrypted,
            **kwargs
        )

        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    def get_user_api_keys(self, user_id: str, provider: str = None,
                          active_only: bool = True) -> List[UserAPIKey]:
        """获取用户API密钥"""
        query = self.db.query(UserAPIKey).filter(UserAPIKey.user_id == user_id)

        if provider:
            query = query.filter(UserAPIKey.provider == provider)

        if active_only:
            query = query.filter(UserAPIKey.is_active == True)

        return query.all()

    def update_api_key_usage(self, api_key_id: str, tokens_used: int, cost: float) -> bool:
        """更新API密钥使用统计"""
        api_key = self.db.query(UserAPIKey).filter(UserAPIKey.id == api_key_id).first()
        if not api_key:
            return False

        api_key.total_tokens_used += tokens_used
        api_key.total_cost += cost
        api_key.total_requests += 1
        api_key.successful_requests += 1
        api_key.last_used = datetime.utcnow()
        api_key.updated_at = datetime.utcnow()

        self.db.commit()
        return True

    # ==================== 系统配置操作 ====================

    def get_system_config(self, key: str) -> Optional[SystemConfig]:
        """获取系统配置"""
        return self.db.query(SystemConfig).filter(SystemConfig.key == key).first()

    def set_system_config(self, key: str, value: Any, description: str = None,
                          category: str = "system") -> SystemConfig:
        """设置系统配置"""
        config = self.get_system_config(key)

        if config:
            config.value = value
            if description:
                config.description = description
            config.updated_at = datetime.utcnow()
        else:
            config = SystemConfig(
                key=key,
                value=value,
                description=description,
                category=category
            )
            self.db.add(config)

        self.db.commit()
        self.db.refresh(config)
        return config

    def get_public_configs(self, category: str = None) -> List[SystemConfig]:
        """获取公开配置"""
        query = self.db.query(SystemConfig).filter(SystemConfig.is_public == True)

        if category:
            query = query.filter(SystemConfig.category == category)

        return query.all()

    # ==================== 任务队列操作 ====================

    def create_task(self, task_id: str, user_id: str, task_type: str,
                    task_data: Dict, priority: int = 0) -> TaskQueue:
        """创建任务"""
        task = TaskQueue(
            task_id=task_id,
            user_id=user_id,
            task_type=task_type,
            task_data=task_data,
            priority=priority
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_pending_tasks(self, task_type: str = None, limit: int = 10) -> List[TaskQueue]:
        """获取待处理任务"""
        query = self.db.query(TaskQueue).filter(TaskQueue.status == "pending")

        if task_type:
            query = query.filter(TaskQueue.task_type == task_type)

        return query.order_by(desc(TaskQueue.priority), TaskQueue.created_at).limit(limit).all()

    def update_task_status(self, task_id: str, status: str,
                           result_data: Dict = None, error_message: str = None,
                           worker_id: str = None) -> bool:
        """更新任务状态"""
        task = self.db.query(TaskQueue).filter(TaskQueue.task_id == task_id).first()
        if not task:
            return False

        task.status = status
        task.updated_at = datetime.utcnow()

        if worker_id:
            task.worker_id = worker_id

        if status == "processing" and not task.started_at:
            task.started_at = datetime.utcnow()

        if status in ["completed", "failed"]:
            task.completed_at = datetime.utcnow()

        if result_data:
            task.result_data = result_data

        if error_message:
            task.error_message = error_message

        self.db.commit()
        return True

    # ==================== 统计和分析 ====================

    def get_system_statistics(self) -> Dict:
        """获取系统统计信息"""
        stats = {}

        # 用户统计
        stats['users'] = {
            'total': self.db.query(User).count(),
            'active_today': self.db.query(User).filter(
                User.last_active >= datetime.utcnow() - timedelta(days=1)
            ).count(),
            'new_this_month': self.db.query(User).filter(
                User.created_at >= datetime.utcnow() - timedelta(days=30)
            ).count()
        }

        # 小说统计
        stats['novels'] = {
            'total': self.db.query(Novel).count(),
            'completed': self.db.query(Novel).filter(Novel.status == 'completed').count(),
            'in_progress': self.db.query(Novel).filter(Novel.status.in_(['generating', 'draft'])).count(),
            'public': self.db.query(Novel).filter(Novel.is_public == True).count()
        }

        # 生成统计
        today = datetime.utcnow().date()
        stats['generation'] = {
            'total_logs': self.db.query(GenerationLog).count(),
            'today_generations': self.db.query(GenerationLog).filter(
                func.date(GenerationLog.created_at) == today
            ).count(),
            'success_rate': self._calculate_success_rate(),
            'total_tokens': self.db.query(func.sum(GenerationLog.tokens_used)).scalar() or 0
        }

        # 模板统计
        stats['templates'] = {
            'total': self.db.query(UserTemplate).count(),
            'public': self.db.query(UserTemplate).filter(UserTemplate.is_public == True).count(),
            'most_used': self.db.query(UserTemplate).order_by(desc(UserTemplate.usage_count)).first()
        }

        return stats

    def _calculate_success_rate(self) -> float:
        """计算成功率"""
        total = self.db.query(GenerationLog).count()
        if total == 0:
            return 0.0

        success = self.db.query(GenerationLog).filter(GenerationLog.status == 'success').count()
        return success / total

    def get_popular_genres(self, limit: int = 10) -> List[Tuple[str, int]]:
        """获取热门类型"""
        result = self.db.query(
            Novel.genre,
            func.count(Novel.id).label('count')
        ).filter(
            Novel.genre.isnot(None)
        ).group_by(Novel.genre).order_by(desc('count')).limit(limit).all()

        return [(genre, count) for genre, count in result]

    def get_user_activity_trend(self, days: int = 30) -> List[Dict]:
        """获取用户活动趋势"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = self.db.query(
            func.date(User.created_at).label('date'),
            func.count(User.id).label('new_users')
        ).filter(
            User.created_at >= cutoff
        ).group_by(func.date(User.created_at)).order_by('date').all()

        return [{'date': str(date), 'new_users': count} for date, count in result]

    # ==================== 清理和维护 ====================

    def cleanup_old_logs(self, days: int = 30) -> int:
        """清理旧日志"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        deleted = self.db.query(GenerationLog).filter(
            GenerationLog.created_at < cutoff
        ).delete()

        self.db.commit()
        return deleted

    def cleanup_failed_tasks(self, days: int = 7) -> int:
        """清理失败任务"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        deleted = self.db.query(TaskQueue).filter(
            TaskQueue.status == 'failed',
            TaskQueue.created_at < cutoff
        ).delete()

        self.db.commit()
        return deleted