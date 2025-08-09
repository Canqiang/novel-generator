from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import bcrypt


class DatabaseOperations:
    """数据库操作封装"""

    def __init__(self, db: Session):
        self.db = db

    # ========== 用户操作 ==========

    def create_user(self, email: str, username: str, password: str) -> User:
        """创建用户"""
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        user = User(
            email=email,
            username=username,
            password_hash=password_hash.decode('utf-8')
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        return self.db.query(User).filter(User.email == email).first()

    def verify_password(self, user: User, password: str) -> bool:
        """验证密码"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            user.password_hash.encode('utf-8')
        )

    def update_user_tokens(self, user_id: str, tokens_used: int) -> None:
        """更新用户Token使用量"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_tokens_used += tokens_used
            self.db.commit()

    # ========== 小说操作 ==========

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

    def get_user_novels(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Novel]:
        """获取用户小说列表"""
        return self.db.query(Novel) \
            .filter(Novel.user_id == user_id) \
            .order_by(Novel.created_at.desc()) \
            .limit(limit) \
            .offset(offset) \
            .all()

    def update_novel_status(self, novel_id: str, status: str) -> None:
        """更新小说状态"""
        novel = self.db.query(Novel).filter(Novel.id == novel_id).first()
        if novel:
            novel.status = status
            novel.updated_at = datetime.utcnow()
            self.db.commit()

    def save_novel_content(self, novel_id: str, outline: dict, chapters: list) -> None:
        """保存小说内容"""
        novel = self.db.query(Novel).filter(Novel.id == novel_id).first()
        if novel:
            novel.outline = outline
            novel.chapters = chapters
            novel.updated_at = datetime.utcnow()
            self.db.commit()

    # ========== 章节操作 ==========

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

    def update_chapter_content(self, chapter_id: str, content: str, word_count: int) -> None:
        """更新章节内容"""
        chapter = self.db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if chapter:
            # 保存旧版本
            if chapter.content:
                chapter.previous_versions.append({
                    'version': chapter.version,
                    'content': chapter.content,
                    'updated_at': chapter.updated_at.isoformat()
                })

            chapter.content = content
            chapter.word_count = word_count
            chapter.version += 1
            chapter.updated_at = datetime.utcnow()
            self.db.commit()

    # ========== 日志操作 ==========

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
        return log

    def get_generation_stats(self, user_id: str, days: int = 30) -> dict:
        """获取生成统计"""
        cutoff = datetime.utcnow() - timedelta(days=days)

        logs = self.db.query(GenerationLog) \
            .filter(GenerationLog.user_id == user_id) \
            .filter(GenerationLog.created_at >= cutoff) \
            .all()

        total_tokens = sum(log.tokens_used or 0 for log in logs)
        total_cost = sum(log.cost or 0 for log in logs)
        success_count = sum(1 for log in logs if log.status == 'success')
        failed_count = sum(1 for log in logs if log.status == 'failed')

        return {
            'total_generations': len(logs),
            'success_count': success_count,
            'failed_count': failed_count,
            'success_rate': success_count / len(logs) if logs else 0,
            'total_tokens': total_tokens,
            'total_cost': total_cost,
            'average_tokens': total_tokens / len(logs) if logs else 0
        }

    # ========== 模板操作 ==========

    def create_template(self, user_id: str, name: str, template_type: str,
                        content: dict) -> UserTemplate:
        """创建用户模板"""
        template = UserTemplate(
            user_id=user_id,
            name=name,
            template_type=template_type,
            content=content
        )

        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template

    def get_user_templates(self, user_id: str, template_type: str = None) -> List[UserTemplate]:
        """获取用户模板"""
        query = self.db.query(UserTemplate).filter(UserTemplate.user_id == user_id)

        if template_type:
            query = query.filter(UserTemplate.template_type == template_type)

        return query.order_by(UserTemplate.usage_count.desc()).all()

    def get_public_templates(self, template_type: str = None, limit: int = 20) -> List[UserTemplate]:
        """获取公开模板"""
        query = self.db.query(UserTemplate).filter(UserTemplate.is_public == True)

        if template_type:
            query = query.filter(UserTemplate.template_type == template_type)

        return query.order_by(UserTemplate.usage_count.desc()).limit(limit).all()


# ==================== 数据库初始化 ====================

def init_database():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 初始化数据库
    init_database()

    # 测试Redis缓存
    cache = RedisCache()

    # 测试任务管理
    task_data = {
        'id': 'test-task-1',
        'status': 'pending',
        'progress': 0
    }
    cache.set_task('test-task-1', task_data)
    print("Task saved:", cache.get_task('test-task-1'))

    # 测试速率限制
    user_id = 'test-user-1'
    for i in range(12):
        allowed = cache.check_rate_limit(user_id, limit=10)
        print(f"Request {i + 1}: {'Allowed' if allowed else 'Blocked'}")

    # 测试数据库操作
    db = SessionLocal()
    db_ops = DatabaseOperations(db)

    # 创建测试用户
    try:
        user = db_ops.create_user(
            email="test@example.com",
            username="testuser",
            password="password123"
        )
        print(f"User created: {user.username}")

        # 创建测试小说
        novel = db_ops.create_novel(
            user_id=str(user.id),
            title="测试小说",
            genre="scifi",
            status="draft"
        )
        print(f"Novel created: {novel.title}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()