import redis
import json
import pickle
import hashlib
import uuid
import time
import logging
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class CacheMetrics:
    """缓存指标"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class RedisCache:
    """增强版Redis缓存管理器"""

    def __init__(self, host: str = None, port: int = None, db: int = None,
                 password: str = None, **kwargs):
        """初始化Redis连接"""
        self.host = host or settings.REDIS_HOST
        self.port = port or settings.REDIS_PORT
        self.db = db or settings.REDIS_DB
        self.password = password or (settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None)

        # 连接池配置
        pool_kwargs = {
            'host': self.host,
            'port': self.port,
            'db': self.db,
            'password': self.password,
            'decode_responses': False,  # 支持二进制数据
            'max_connections': kwargs.get('max_connections', settings.REDIS_MAX_CONNECTIONS),
            'retry_on_timeout': True,
            'socket_keepalive': True,
            'socket_keepalive_options': {},
            'health_check_interval': 30,
        }

        try:
            self.connection_pool = redis.ConnectionPool(**pool_kwargs)
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)

            # 测试连接
            self.redis_client.ping()
            logger.info(f"Redis连接成功: {self.host}:{self.port}/{self.db}")

        except redis.ConnectionError as e:
            logger.error(f"Redis连接失败: {e}")
            # 如果Redis连接失败，使用内存缓存作为后备
            self._fallback_cache = {}
            self.redis_client = None
            logger.warning("使用内存缓存作为Redis后备方案")

        # 缓存指标
        self.metrics = CacheMetrics()

        # 键前缀
        self.key_prefix = "novel_generator"

        # 序列化选项
        self.use_compression = kwargs.get('use_compression', False)
        self.default_ttl = kwargs.get('default_ttl', settings.CACHE_TTL)

    def _make_key(self, prefix: str, identifier: str) -> str:
        """生成缓存键"""
        return f"{self.key_prefix}:{prefix}:{identifier}"

    def _serialize(self, value: Any) -> bytes:
        """序列化数据"""
        try:
            # 优先使用JSON序列化（更快，占用空间小）
            json_str = json.dumps(value, ensure_ascii=False, default=str)
            data = json_str.encode('utf-8')

            # 如果启用压缩且数据较大
            if self.use_compression and len(data) > 1024:
                import zlib
                data = zlib.compress(data)
                return b'compressed:' + data

            return b'json:' + data

        except (TypeError, ValueError):
            # JSON序列化失败，使用pickle
            try:
                data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

                if self.use_compression and len(data) > 1024:
                    import zlib
                    data = zlib.compress(data)
                    return b'compressed_pickle:' + data

                return b'pickle:' + data

            except Exception as e:
                logger.error(f"序列化失败: {e}")
                raise

    def _deserialize(self, value: bytes) -> Any:
        """反序列化数据"""
        if value is None:
            return None

        try:
            # 检查数据类型标记
            if value.startswith(b'compressed:'):
                import zlib
                data = zlib.decompress(value[11:])  # 去除'compressed:'前缀
                return json.loads(data.decode('utf-8'))

            elif value.startswith(b'compressed_pickle:'):
                import zlib
                data = zlib.decompress(value[18:])  # 去除'compressed_pickle:'前缀
                return pickle.loads(data)

            elif value.startswith(b'json:'):
                data = value[5:]  # 去除'json:'前缀
                return json.loads(data.decode('utf-8'))

            elif value.startswith(b'pickle:'):
                data = value[7:]  # 去除'pickle:'前缀
                return pickle.loads(data)

            else:
                # 兼容旧格式，尝试JSON然后pickle
                try:
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return pickle.loads(value)

        except Exception as e:
            logger.error(f"反序列化失败: {e}")
            return None

    @contextmanager
    def _handle_redis_error(self):
        """Redis错误处理上下文管理器"""
        try:
            if self.redis_client is None:
                yield None
            else:
                yield self.redis_client
        except redis.RedisError as e:
            logger.warning(f"Redis操作失败，使用后备方案: {e}")
            yield None

    # ==================== 基础缓存操作 ====================

    def set(self, key: str, value: Any, expire: int = None) -> bool:
        """设置缓存"""
        full_key = self._make_key("cache", key)
        expire = expire or self.default_ttl

        try:
            with self._handle_redis_error() as client:
                if client:
                    serialized_value = self._serialize(value)
                    result = client.setex(full_key, expire, serialized_value)
                    self.metrics.sets += 1
                    return bool(result)
                else:
                    # 使用内存后备
                    self._fallback_cache[full_key] = {
                        'value': value,
                        'expires_at': time.time() + expire
                    }
                    self.metrics.sets += 1
                    return True

        except Exception as e:
            logger.error(f"设置缓存失败 {key}: {e}")
            return False

    def get(self, key: str) -> Any:
        """获取缓存"""
        full_key = self._make_key("cache", key)

        try:
            with self._handle_redis_error() as client:
                if client:
                    value = client.get(full_key)
                    if value is not None:
                        self.metrics.hits += 1
                        return self._deserialize(value)
                    else:
                        self.metrics.misses += 1
                        return None
                else:
                    # 使用内存后备
                    cached = self._fallback_cache.get(full_key)
                    if cached and cached['expires_at'] > time.time():
                        self.metrics.hits += 1
                        return cached['value']
                    else:
                        if cached:
                            del self._fallback_cache[full_key]
                        self.metrics.misses += 1
                        return None

        except Exception as e:
            logger.error(f"获取缓存失败 {key}: {e}")
            self.metrics.misses += 1
            return None

    def delete(self, key: str) -> bool:
        """删除缓存"""
        full_key = self._make_key("cache", key)

        try:
            with self._handle_redis_error() as client:
                if client:
                    result = client.delete(full_key)
                    self.metrics.deletes += 1
                    return bool(result)
                else:
                    # 使用内存后备
                    if full_key in self._fallback_cache:
                        del self._fallback_cache[full_key]
                        self.metrics.deletes += 1
                        return True
                    return False

        except Exception as e:
            logger.error(f"删除缓存失败 {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        full_key = self._make_key("cache", key)

        try:
            with self._handle_redis_error() as client:
                if client:
                    return bool(client.exists(full_key))
                else:
                    cached = self._fallback_cache.get(full_key)
                    return cached is not None and cached['expires_at'] > time.time()

        except Exception as e:
            logger.error(f"检查键存在失败 {key}: {e}")
            return False

    def ttl(self, key: str) -> int:
        """获取键的剩余生存时间"""
        full_key = self._make_key("cache", key)

        try:
            with self._handle_redis_error() as client:
                if client:
                    return client.ttl(full_key)
                else:
                    cached = self._fallback_cache.get(full_key)
                    if cached:
                        remaining = cached['expires_at'] - time.time()
                        return max(0, int(remaining))
                    return -2  # 键不存在

        except Exception as e:
            logger.error(f"获取TTL失败 {key}: {e}")
            return -1

    # ==================== 任务管理 ====================

    def set_task(self, task_id: str, task_data: Dict, expire: int = None) -> bool:
        """设置任务数据"""
        key = self._make_key("task", task_id)
        expire = expire or 7200  # 任务默认保存2小时

        # 添加时间戳
        task_data = task_data.copy()
        task_data['cached_at'] = datetime.now().isoformat()

        try:
            with self._handle_redis_error() as client:
                if client:
                    serialized = self._serialize(task_data)
                    return bool(client.setex(key, expire, serialized))
                else:
                    self._fallback_cache[key] = {
                        'value': task_data,
                        'expires_at': time.time() + expire
                    }
                    return True

        except Exception as e:
            logger.error(f"设置任务失败 {task_id}: {e}")
            return False

    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务数据"""
        key = self._make_key("task", task_id)

        try:
            with self._handle_redis_error() as client:
                if client:
                    value = client.get(key)
                    return self._deserialize(value) if value else None
                else:
                    cached = self._fallback_cache.get(key)
                    if cached and cached['expires_at'] > time.time():
                        return cached['value']
                    return None

        except Exception as e:
            logger.error(f"获取任务失败 {task_id}: {e}")
            return None

    def update_task_status(self, task_id: str, status: str, progress: int = None,
                           error: str = None, **kwargs) -> bool:
        """更新任务状态"""
        task = self.get_task(task_id)
        if not task:
            return False

        # 更新字段
        task['status'] = status
        task['updated_at'] = datetime.now().isoformat()

        if progress is not None:
            task['progress'] = progress
        if error is not None:
            task['error'] = error

        # 合并其他参数
        task.update(kwargs)

        return self.set_task(task_id, task)

    def get_task_list(self, status: str = None, limit: int = 100) -> List[Dict]:
        """获取任务列表"""
        pattern = self._make_key("task", "*")
        tasks = []

        try:
            with self._handle_redis_error() as client:
                if client:
                    keys = client.keys(pattern)
                    for key in keys[:limit]:
                        task_data = self._deserialize(client.get(key))
                        if task_data and (not status or task_data.get('status') == status):
                            tasks.append(task_data)
                else:
                    # 内存后备方案
                    for key, cached in self._fallback_cache.items():
                        if key.startswith(self._make_key("task", "")):
                            if cached['expires_at'] > time.time():
                                task_data = cached['value']
                                if not status or task_data.get('status') == status:
                                    tasks.append(task_data)

        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")

        return sorted(tasks, key=lambda x: x.get('created_at', ''), reverse=True)

    # ==================== 结果缓存 ====================

    def cache_prompt_result(self, prompt: str, result: str, expire: int = None) -> bool:
        """缓存提示词结果"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        key = self._make_key("prompt_cache", prompt_hash)
        expire = expire or settings.RESULT_CACHE_TTL

        cache_data = {
            'prompt': prompt[:200],  # 保存前200字符用于调试
            'result': result,
            'cached_at': datetime.now().isoformat(),
            'hash': prompt_hash
        }

        return self.set(f"prompt_{prompt_hash}", cache_data, expire)

    def get_cached_prompt_result(self, prompt: str) -> Optional[str]:
        """获取缓存的提示词结果"""
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()
        cached = self.get(f"prompt_{prompt_hash}")

        if cached and isinstance(cached, dict):
            return cached.get('result')
        return cached  # 兼容旧格式

    # ==================== 用户限流 ====================

    def check_rate_limit(self, user_id: str, limit: int = 10, window: int = 3600) -> bool:
        """检查用户速率限制"""
        key = self._make_key("rate_limit", f"{user_id}:{window}")

        try:
            with self._handle_redis_error() as client:
                if client:
                    current = client.incr(key)
                    if current == 1:
                        client.expire(key, window)
                    return current <= limit
                else:
                    # 简化的内存限流
                    now = time.time()
                    window_start = now - window

                    # 清理过期记录
                    if not hasattr(self, '_rate_limit_cache'):
                        self._rate_limit_cache = {}

                    user_requests = self._rate_limit_cache.get(user_id, [])
                    user_requests = [req_time for req_time in user_requests if req_time > window_start]

                    if len(user_requests) < limit:
                        user_requests.append(now)
                        self._rate_limit_cache[user_id] = user_requests
                        return True
                    return False

        except Exception as e:
            logger.error(f"速率限制检查失败: {e}")
            return True  # 错误时不阻止用户

    def get_rate_limit_status(self, user_id: str, window: int = 3600) -> Dict:
        """获取用户限流状态"""
        key = self._make_key("rate_limit", f"{user_id}:{window}")

        try:
            with self._handle_redis_error() as client:
                if client:
                    current = client.get(key)
                    ttl = client.ttl(key)
                    return {
                        'current_requests': int(current) if current else 0,
                        'reset_in_seconds': ttl if ttl > 0 else 0
                    }
                else:
                    # 内存后备
                    user_requests = getattr(self, '_rate_limit_cache', {}).get(user_id, [])
                    window_start = time.time() - window
                    current_requests = len([req for req in user_requests if req > window_start])

                    return {
                        'current_requests': current_requests,
                        'reset_in_seconds': window if current_requests > 0 else 0
                    }

        except Exception as e:
            logger.error(f"获取限流状态失败: {e}")
            return {'current_requests': 0, 'reset_in_seconds': 0}

    # ==================== Token使用统计 ====================

    def increment_user_tokens(self, user_id: str, tokens: int, date: str = None) -> int:
        """增加用户Token使用量"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = self._make_key(f"tokens:{date}", user_id)

        try:
            with self._handle_redis_error() as client:
                if client:
                    new_total = client.incrby(key, tokens)
                    client.expire(key, 86400 * 7)  # 保留7天
                    return int(new_total)
                else:
                    # 内存后备
                    if not hasattr(self, '_token_cache'):
                        self._token_cache = {}

                    current = self._token_cache.get(key, 0)
                    new_total = current + tokens
                    self._token_cache[key] = new_total
                    return new_total

        except Exception as e:
            logger.error(f"更新Token使用量失败: {e}")
            return tokens

    def get_user_token_usage(self, user_id: str, date: str = None) -> int:
        """获取用户Token使用量"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        key = self._make_key(f"tokens:{date}", user_id)

        try:
            with self._handle_redis_error() as client:
                if client:
                    usage = client.get(key)
                    return int(usage) if usage else 0
                else:
                    return getattr(self, '_token_cache', {}).get(key, 0)

        except Exception as e:
            logger.error(f"获取Token使用量失败: {e}")
            return 0

    # ==================== 分布式锁 ====================

    def acquire_lock(self, lock_name: str, timeout: int = 10, expire: int = 30) -> Optional[str]:
        """获取分布式锁"""
        key = self._make_key("lock", lock_name)
        identifier = str(uuid.uuid4())

        try:
            with self._handle_redis_error() as client:
                if client:
                    end_time = time.time() + timeout
                    while time.time() < end_time:
                        if client.set(key, identifier, nx=True, ex=expire):
                            return identifier
                        time.sleep(0.001)
                    return None
                else:
                    # 简化的内存锁
                    if not hasattr(self, '_lock_cache'):
                        self._lock_cache = {}

                    if key not in self._lock_cache:
                        self._lock_cache[key] = {
                            'identifier': identifier,
                            'expires_at': time.time() + expire
                        }
                        return identifier

                    # 检查锁是否过期
                    lock_info = self._lock_cache[key]
                    if lock_info['expires_at'] < time.time():
                        self._lock_cache[key] = {
                            'identifier': identifier,
                            'expires_at': time.time() + expire
                        }
                        return identifier

                    return None

        except Exception as e:
            logger.error(f"获取锁失败 {lock_name}: {e}")
            return None

    def release_lock(self, lock_name: str, identifier: str) -> bool:
        """释放分布式锁"""
        key = self._make_key("lock", lock_name)

        try:
            with self._handle_redis_error() as client:
                if client:
                    # 原子操作：检查标识符并删除
                    lua_script = """
                    if redis.call("get", KEYS[1]) == ARGV[1] then
                        return redis.call("del", KEYS[1])
                    else
                        return 0
                    end
                    """
                    return bool(client.eval(lua_script, 1, key, identifier))
                else:
                    # 内存锁释放
                    if hasattr(self, '_lock_cache') and key in self._lock_cache:
                        lock_info = self._lock_cache[key]
                        if lock_info['identifier'] == identifier:
                            del self._lock_cache[key]
                            return True
                    return False

        except Exception as e:
            logger.error(f"释放锁失败 {lock_name}: {e}")
            return False

    # ==================== 统计和监控 ====================

    def get_cache_info(self) -> Dict:
        """获取缓存信息"""
        info = {
            'metrics': asdict(self.metrics),
            'connection': {
                'host': self.host,
                'port': self.port,
                'db': self.db,
                'connected': self.redis_client is not None
            },
            'memory_fallback_keys': len(getattr(self, '_fallback_cache', {}))
        }

        try:
            with self._handle_redis_error() as client:
                if client:
                    redis_info = client.info()
                    info['redis'] = {
                        'version': redis_info.get('redis_version'),
                        'memory_used': redis_info.get('used_memory_human'),
                        'connected_clients': redis_info.get('connected_clients'),
                        'keyspace_hits': redis_info.get('keyspace_hits', 0),
                        'keyspace_misses': redis_info.get('keyspace_misses', 0)
                    }
        except Exception as e:
            logger.error(f"获取Redis信息失败: {e}")

        return info

    def clear_cache(self, pattern: str = "*") -> int:
        """清理缓存"""
        full_pattern = self._make_key("cache", pattern)
        deleted = 0

        try:
            with self._handle_redis_error() as client:
                if client:
                    keys = client.keys(full_pattern)
                    if keys:
                        deleted = client.delete(*keys)
                else:
                    # 清理内存缓存
                    keys_to_delete = [
                        key for key in self._fallback_cache.keys()
                        if key.startswith(self._make_key("cache", ""))
                    ]
                    for key in keys_to_delete:
                        del self._fallback_cache[key]
                    deleted = len(keys_to_delete)

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")

        return deleted

    def health_check(self) -> Dict:
        """健康检查"""
        status = {
            'redis_available': False,
            'memory_fallback': False,
            'latency_ms': None,
            'error': None
        }

        try:
            with self._handle_redis_error() as client:
                if client:
                    start_time = time.time()
                    client.ping()
                    latency = (time.time() - start_time) * 1000

                    status.update({
                        'redis_available': True,
                        'latency_ms': round(latency, 2)
                    })
                else:
                    status['memory_fallback'] = True

        except Exception as e:
            status['error'] = str(e)

        return status


# ==================== 全局实例 ====================

# 创建全局缓存实例
cache_instance = None


def get_cache() -> RedisCache:
    """获取缓存实例（单例模式）"""
    global cache_instance
    if cache_instance is None:
        cache_instance = RedisCache()
    return cache_instance


# ==================== 装饰器 ====================

def cached(key_func=None, expire=None):
    """缓存装饰器"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名和参数生成键
                import hashlib
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func.__name__}:{hashlib.md5(args_str.encode()).hexdigest()}"

            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                return result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.set(cache_key, result, expire)
            return result

        return wrapper

    return decorator


if __name__ == "__main__":
    # 测试缓存功能
    cache = RedisCache()

    # 基础测试
    cache.set("test_key", {"message": "Hello, World!"})
    result = cache.get("test_key")
    print(f"缓存测试: {result}")

    # 健康检查
    health = cache.health_check()
    print(f"健康状态: {health}")

    # 缓存信息
    info = cache.get_cache_info()
    print(f"缓存信息: {info}")