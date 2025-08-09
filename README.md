# AI小说生成系统 - 部署指南

## 项目结构

```
novel-generator/
├── backend/
│   ├── main.py              # FastAPI主应用
│   ├── novel_generator.py   # 核心生成逻辑
│   ├── prompt_templates.py  # 提示词模板
│   ├── database.py         # 数据库连接
│   ├── redis_cache.py      # Redis缓存
│   ├── requirements.txt    # Python依赖
│   └── .env                # 环境变量
├── frontend/
│   ├── src/
│   │   ├── App.js         # React主组件
│   │   ├── index.js       # 入口文件
│   │   └── components/    # 组件目录
│   ├── package.json       # Node依赖
│   └── .env.local        # 前端环境变量
└── docker-compose.yml     # Docker编排
```

## 一、后端配置

### 1. 安装依赖

创建 `requirements.txt`:

```txt
fastapi==0.104.1
uvicorn==0.24.0
openai==1.3.0
python-dotenv==1.0.0
pydantic==2.5.0
redis==5.0.1
tiktoken==0.5.1
tenacity==8.2.3
python-multipart==0.0.6
aiofiles==23.2.1
```

安装：
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 环境变量配置

创建 `.env` 文件：

```env
# OpenAI配置
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo-16k
OPENAI_TEMPERATURE=0.8

# 其他LLM选项（可选）
ANTHROPIC_API_KEY=your-claude-key
DASHSCOPE_API_KEY=your-qwen-key  # 通义千问
MOONSHOT_API_KEY=your-moonshot-key  # 月之暗面

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 应用配置
APP_SECRET_KEY=your-secret-key-here
APP_DEBUG=True
APP_PORT=8000

# Token限制
MAX_TOKENS_PER_REQUEST=50000
MAX_CONCURRENT_TASKS=5
RATE_LIMIT_PER_HOUR=10
```

### 3. Redis安装（用于任务队列）

```bash
# Docker方式
docker run -d --name redis -p 6379:6379 redis:alpine

# 或本地安装
# Mac: brew install redis
# Ubuntu: sudo apt-get install redis-server
# Windows: 下载安装包
```

### 4. 启动后端
在启动前请确保已设置 `OPENAI_API_KEY` 环境变量：

```bash
cd backend
export OPENAI_API_KEY=sk-your-api-key  # 或在环境中预先设置
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 二、前端配置

### 1. 创建React项目

```bash
npx create-react-app frontend
cd frontend
```

### 2. 安装依赖

修改 `package.json`:

```json
{
  "name": "novel-generator-frontend",
  "version": "1.0.0",
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.263.1",
    "axios": "^1.5.0",
    "tailwindcss": "^3.3.5",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.31"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  },
  "proxy": "http://localhost:8000"
}
```

安装：
```bash
npm install
```

### 3. 配置Tailwind CSS

创建 `tailwind.config.js`:

```javascript
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

创建 `src/index.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 4. 启动前端

```bash
cd frontend
npm start
```

## 三、Docker部署（推荐）

### docker-compose.yml

```yaml
version: '3.8'

services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_HOST=redis
    depends_on:
      - redis
    volumes:
      - ./backend:/app

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - REACT_APP_API_URL=http://localhost:8000

volumes:
  redis_data:
```

### Backend Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

RUN npm run build

RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "3000"]
```

### 一键部署

```bash
# 设置环境变量
export OPENAI_API_KEY=your-key-here

# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 四、生产环境优化

### 1. 数据库持久化

添加 PostgreSQL 存储任务历史：

```python
# database.py
from sqlalchemy import create_engine, Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://user:password@localhost/novels"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Novel(Base):
    __tablename__ = "novels"
    
    id = Column(String, primary_key=True)
    title = Column(String)
    content = Column(JSON)
    created_at = Column(DateTime)
    user_id = Column(String)
```

### 2. 性能优化

```python
# 使用异步任务队列
from celery import Celery

celery_app = Celery(
    'novel_generator',
    broker='redis://localhost:6379',
    backend='redis://localhost:6379'
)

@celery_app.task
def generate_novel_task(request_data):
    generator = NovelGenerator(api_key=os.getenv("OPENAI_API_KEY"))
    return generator.generate_novel(request_data)
```

### 3. 成本控制

```python
# token_manager.py
class TokenManager:
    def __init__(self, daily_limit=1000000):
        self.daily_limit = daily_limit
        self.redis_client = redis.Redis()
    
    def check_limit(self, user_id):
        key = f"tokens:{user_id}:{datetime.now().date()}"
        used = self.redis_client.get(key) or 0
        return int(used) < self.daily_limit
    
    def update_usage(self, user_id, tokens):
        key = f"tokens:{user_id}:{datetime.now().date()}"
        self.redis_client.incrby(key, tokens)
        self.redis_client.expire(key, 86400)  # 24小时过期
```

### 4. 监控和日志

```python
# logging_config.py
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 文件日志
    file_handler = RotatingFileHandler(
        'novel_generator.log',
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # 控制台日志
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
```

## 五、API使用示例

### 1. 生成小说

```bash
curl -X POST http://localhost:8000/api/novel/generate \
  -H "Content-Type: application/json" \
  -d '{
    "theme": "一个程序员发现AI产生了自我意识",
    "genre": "scifi",
    "style": "知乎风格"
  }'
```

### 2. 查询状态

```bash
curl http://localhost:8000/api/novel/status/{task_id}
```

### 3. 获取结果

```bash
curl http://localhost:8000/api/novel/result/{task_id}
```

### 4. 导出小说

```bash
curl -X POST http://localhost:8000/api/novel/export/{task_id} \
  -H "Content-Type: application/json" \
  -d '{"format": "markdown"}'
```

## 六、成本估算

| 模型 | 输入价格 | 输出价格 | 3万字成本 |
|-----|---------|---------|----------|
| GPT-3.5-16k | $0.003/1K | $0.004/1K | ~$2.5 |
| GPT-4 | $0.03/1K | $0.06/1K | ~$25 |
| Claude-2 | $0.008/1K | $0.024/1K | ~$15 |
| 通义千问 | ¥0.008/1K | ¥0.012/1K | ~¥15 |

## 七、常见问题

### Q1: Token超限怎么办？
- 使用更长上下文的模型（如GPT-3.5-16k）
- 实施滑动窗口压缩策略
- 分批生成，保存中间状态

### Q2: 生成速度太慢？
- 使用并发请求（注意rate limit）
- 降低单次生成的字数
- 使用流式输出

### Q3: 内容质量不稳定？
- 调整temperature参数（0.7-0.85最佳）
- 使用多次生成取最优
- 增加人工审核环节

### Q4: 如何降低成本？
- 使用GPT-3.5代替GPT-4
- 缓存常用的大纲模板
- 批量处理请求

## 八、扩展功能

### 1. 多模型支持

```python
class MultiModelGenerator:
    def __init__(self):
        self.models = {
            'openai': OpenAIGenerator(),
            'anthropic': ClaudeGenerator(),
            'qwen': QwenGenerator(),
        }
    
    async def generate(self, request, model='openai'):
        return await self.models[model].generate(request)
```

### 2. 用户系统

```python
from fastapi_users import FastAPIUsers

# 添加用户认证
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)
```

### 3. 支付集成

```python
import stripe

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.post("/api/payment/checkout")
async def create_checkout_session(request: PaymentRequest):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': 'Novel Generation',
                },
                'unit_amount': 299,  # $2.99
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url='http://localhost:3000/success',
        cancel_url='http://localhost:3000/cancel',
    )
    return {"checkout_url": session.url}
```

## 九、上线清单

- [ ] 配置HTTPS证书
- [ ] 设置环境变量
- [ ] 配置域名
- [ ] 设置备份策略
- [ ] 配置监控告警
- [ ] 压力测试
- [ ] 安全审计
- [ ] 用户协议和隐私政策
- [ ] 客服系统
- [ ] 数据分析埋点

---

祝你的小说生成系统上线顺利！如有问题，请查看项目Wiki或提交Issue。