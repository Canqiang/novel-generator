# redis_cache.py
import redis
import json
import pickle
from typing import Any, Optional
from datetime import timedelta, datetime
import hashlib


class RedisCache:
    """Redis缓存管理器"""

    def __init__(self, host='localhost', port=6379, db=0, password=None):
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # 返回bytes以支持pickle
        )

    def _make_key(self, prefix: str, identifier: str) -> str:
        """生成缓存键"""
        return f"{prefix}:{identifier}"

    def _serialize(self, value: Any) -> bytes:
        """序列化数据"""
        try:
            # 尝试JSON序列化（更快）
            return json.dumps(value).encode('utf-8')
        except (TypeError, ValueError):
            # 失败则使用pickle
            return pickle.dumps(value)

    def _deserialize(self, value: bytes) -> Any:
        """反序列化数据"""
        if value is None:
            return None
        try:
            # 尝试JSON反序列化
            return json.loads(value.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # 失败则使用pickle
            return pickle.loads(value)

    # ========== 任务管理 ==========

    def set_task(self, task_id: str, task_data: dict, expire: int = 3600) -> None:
        """设置任务数据"""
        key = self._make_key("task", task_id)
        self.redis_client.setex(
            key,
            expire,
            self._serialize(task_data)
        )

    def get_task(self, task_id: str) -> Optional[dict]:
        """获取任务数据"""
        key = self._make_key("task", task_id)
        value = self.redis_client.get(key)
        return self._deserialize(value)

    def update_task_status(self, task_id: str, status: str, progress: int = None,
                           error: str = None) -> None:
        """更新任务状态"""
        task = self.get_task(task_id) or {}
        task['status'] = status
        if progress is not None:
            task['progress'] = progress
        if error is not None:
            task['error'] = error
        task['updated_at'] = datetime.utcnow().isoformat()
        self.set_task(task_id, task)

    # ========== 结果缓存 ==========

    def cache_prompt_result(self, prompt: str, result: str, expire: int = 86400) -> None:
        """缓存提示词结果（避免重复生成）"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        key = self._make_key("prompt_cache", prompt_hash)
        self.redis_client.setex(key, expire, self._serialize(result))

    def get_cached_prompt_result(self, prompt: str) -> Optional[str]:
        """获取缓存的提示词结果"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        key = self._make_key("prompt_cache", prompt_hash)
        return self._deserialize(self.redis_client.get(key))

    # ========== 用户限流 ==========

    def check_rate_limit(self, user_id: str, limit: int = 10, window: int = 3600) -> bool:
        """检查用户速率限制"""
        key = self._make_key("rate_limit", user_id)

        try:
            current = self.redis_client.incr(key)
            if current == 1:
                self.redis_client.expire(key, window)
            return current <= limit
        except redis.RedisError:
            return True  # Redis错误时不阻止用户

    def get_user_token_usage(self, user_id: str, date: str = None) -> int:
        """获取用户Token使用量"""
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        key = self._make_key(f"tokens:{date}", user_id)
        usage = self.redis_client.get(key)
        return int(usage) if usage else 0

    def increment_user_tokens(self, user_id: str, tokens: int) -> None:
        """增加用户Token使用量"""
        date = datetime.utcnow().strftime("%Y-%m-%d")
        key = self._make_key(f"tokens:{date}", user_id)

        self.redis_client.incrby(key, tokens)
        self.redis_client.expire(key, 86400 * 7)  # 保留7天

    # ========== 会话管理 ==========

    def save_generation_context(self, session_id: str, context: dict, expire: int = 7200) -> None:
        """保存生成上下文"""
        key = self._make_key("context", session_id)
        self.redis_client.setex(key, expire, self._serialize(context))

    def get_generation_context(self, session_id: str) -> Optional[dict]:
        """获取生成上下文"""
        key = self._make_key("context", session_id)
        return self._deserialize(self.redis_client.get(key))

    # ========== 队列管理 ==========

    def push_to_queue(self, queue_name: str, task: dict) -> None:
        """推送任务到队列"""
        key = self._make_key("queue", queue_name)
        self.redis_client.rpush(key, self._serialize(task))

    def pop_from_queue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """从队列弹出任务"""
        key = self._make_key("queue", queue_name)
        if timeout > 0:
            result = self.redis_client.blpop(key, timeout=timeout)
            if result:
                return self._deserialize(result[1])
        else:
            result = self.redis_client.lpop(key)
            if result:
                return self._deserialize(result)
        return None

    def get_queue_length(self, queue_name: str) -> int:
        """获取队列长度"""
        key = self._make_key("queue", queue_name)
        return self.redis_client.llen(key)

    # ========== 分布式锁 ==========

    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """获取分布式锁"""
        key = self._make_key("lock", lock_name)
        identifier = str(uuid.uuid4())

        end = time.time() + timeout
        while time.time() < end:
            if self.redis_client.set(key, identifier, nx=True, ex=timeout):
                return True
            time.sleep(0.001)
        return False

    def release_lock(self, lock_name: str) -> bool:
        """释放分布式锁"""
        key = self._make_key("lock", lock_name)
        return bool(self.redis_client.delete(key))

    # ========== 统计功能 ==========

    def increment_counter(self, counter_name: str, amount: int = 1) -> int:
        """增加计数器"""
        key = self._make_key("counter", counter_name)
        return self.redis_client.incrby(key, amount)

    def get_counter(self, counter_name: str) -> int:
        """获取计数器值"""
        key = self._make_key("counter", counter_name)
        value = self.redis_client.get(key)
        return int(value) if value else 0

    def record_metric(self, metric_name: str, value: float) -> None:
        """记录指标"""
        timestamp = datetime.utcnow().timestamp()
        key = self._make_key("metric", metric_name)
        self.redis_client.zadd(key, {str(timestamp): value})

        # 只保留最近24小时的数据
        cutoff = timestamp - 86400
        self.redis_client.zremrangebyscore(key, 0, cutoff)

    def get_metrics(self, metric_name: str, hours: int = 24) -> list:
        """获取指标数据"""
        key = self._make_key("metric", metric_name)
        cutoff = datetime.utcnow().timestamp() - (hours * 3600)

        results = self.redis_client.zrangebyscore(key, cutoff, '+inf', withscores=True)
        return [(float(timestamp), score) for timestamp, score in results]
