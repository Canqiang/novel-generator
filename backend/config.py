import os
from typing import Dict, Any
from pydantic import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "AI小说生成系统"
    APP_VERSION: str = "1.0.0"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"

    # 安全配置
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    CORS_ORIGINS: list = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # LLM API配置
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-3.5-turbo-16k"
    OPENAI_TEMPERATURE: float = 0.8
    OPENAI_MAX_TOKENS: int = 2000

    # 其他LLM配置
    ANTHROPIC_API_KEY: str = ""
    DASHSCOPE_API_KEY: str = ""  # 通义千问
    MOONSHOT_API_KEY: str = ""  # 月之暗面

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_MAX_CONNECTIONS: int = 20

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./novels.db"
    DATABASE_ECHO: bool = False

    # 业务限制配置
    MAX_TOKENS_PER_REQUEST: int = 50000
    MAX_CONCURRENT_TASKS: int = 5
    RATE_LIMIT_PER_HOUR: int = 10
    DEFAULT_WORD_COUNT: int = 30000
    DEFAULT_CHAPTER_COUNT: int = 12

    # Agent配置
    AGENT_MAX_ITERATIONS: int = 3
    AGENT_REVIEW_THRESHOLD: float = 0.7
    AGENT_COLLABORATION_ENABLED: bool = True

    # 缓存配置
    CACHE_TTL: int = 3600
    RESULT_CACHE_TTL: int = 86400

    class Config:
        env_file = ".env"
        case_sensitive = True


# 小说生成配置
NOVEL_CONFIG = {
    "genres": {
        "urban_romance": {
            "name": "都市情感",
            "description": "现代都市背景的情感故事",
            "style_prompts": {
                "character": "注重人物心理描写，情感细腻",
                "plot": "生活化情节，贴近现实",
                "language": "现代流畅，适合都市读者"
            }
        },
        "mystery": {
            "name": "悬疑推理",
            "description": "充满谜团和反转的推理故事",
            "style_prompts": {
                "character": "理性冷静的主角，复杂的配角",
                "plot": "层层递进，多重反转",
                "language": "紧凑有力，营造悬疑氛围"
            }
        },
        "scifi": {
            "name": "科幻",
            "description": "未来世界或科技背景的故事",
            "style_prompts": {
                "character": "富有想象力，具备科学思维",
                "plot": "科技元素驱动情节",
                "language": "兼具科学性和文学性"
            }
        },
        "workplace": {
            "name": "职场成长",
            "description": "职场背景的成长故事",
            "style_prompts": {
                "character": "职场新人到资深人士的成长",
                "plot": "职场挑战与人际关系",
                "language": "专业而不失人情味"
            }
        },
        "fantasy": {
            "name": "奇幻",
            "description": "魔法或超自然元素的幻想故事",
            "style_prompts": {
                "character": "具备特殊能力或使命",
                "plot": "冒险与成长并重",
                "language": "富有想象力，构建独特世界观"
            }
        }
    },

    "writing_styles": {
        "zhihu": {
            "name": "知乎风格",
            "characteristics": [
                "开篇抓人眼球",
                "逻辑清晰",
                "适当加入思考和见解",
                "贴近生活",
                "有一定知识含量"
            ],
            "language_features": [
                "现代白话文",
                "偶尔使用网络用语",
                "多用短句",
                "注重可读性"
            ]
        },
        "humorous": {
            "name": "轻松幽默",
            "characteristics": [
                "语言轻松活泼",
                "适当的幽默元素",
                "正能量导向",
                "不失深度"
            ]
        },
        "literary": {
            "name": "文艺细腻",
            "characteristics": [
                "文字优美",
                "意境深远",
                "注重情感表达",
                "富有诗意"
            ]
        },
        "suspenseful": {
            "name": "紧张刺激",
            "characteristics": [
                "节奏紧凑",
                "悬念迭起",
                "情节跌宕",
                "引人入胜"
            ]
        }
    }
}

# Agent角色配置
AGENT_ROLES = {
    "planner": {
        "name": "策划师",
        "description": "负责故事大纲和结构设计",
        "responsibilities": [
            "分析用户需求",
            "设计故事结构",
            "规划章节大纲",
            "确定核心冲突"
        ],
        "prompt_style": "逻辑性强，结构化思考"
    },

    "writer": {
        "name": "创作者",
        "description": "负责具体内容创作",
        "responsibilities": [
            "根据大纲创作内容",
            "塑造人物形象",
            "推进情节发展",
            "营造氛围"
        ],
        "prompt_style": "富有想象力，文笔流畅"
    },

    "editor": {
        "name": "编辑",
        "description": "负责内容审核和优化",
        "responsibilities": [
            "检查逻辑一致性",
            "优化语言表达",
            "调整节奏",
            "提升质量"
        ],
        "prompt_style": "批判性思维，注重细节"
    },

    "reviewer": {
        "name": "评审者",
        "description": "负责质量评估和反馈",
        "responsibilities": [
            "评估内容质量",
            "提出改进建议",
            "检查是否符合要求",
            "给出评分"
        ],
        "prompt_style": "客观公正，专业评价"
    }
}

# 提示词模板配置
PROMPT_TEMPLATES = {
    "system_prompts": {
        "planner": """你是一位专业的小说策划编辑，具有丰富的故事创作经验。
你的任务是根据用户需求设计完整的故事大纲，包括：
1. 分析用户需求和题材特点
2. 设计引人入胜的故事结构
3. 规划各章节的核心内容
4. 确保故事逻辑性和吸引力

请始终保持专业性，确保大纲具有实际操作价值。""",

        "writer": """你是一位才华横溢的小说创作者，擅长各种类型的故事创作。
你的任务是根据提供的大纲创作高质量的小说内容，包括：
1. 丰富的人物刻画
2. 生动的场景描写
3. 流畅的情节推进
4. 符合风格要求的语言

请确保创作的内容引人入胜，符合目标读者的期待。""",

        "editor": """你是一位经验丰富的文学编辑，具有敏锐的文学判断力。
你的任务是审核和优化小说内容，包括：
1. 检查逻辑一致性和时间线
2. 优化语言表达和文字流畅度
3. 调整情节节奏和张力
4. 确保人物性格的一致性

请提供具体的修改建议和优化方案。""",

        "reviewer": """你是一位专业的文学评审者，具有客观公正的评价能力。
你的任务是评估小说内容的质量，包括：
1. 故事完整性和逻辑性
2. 人物塑造的深度和可信度  
3. 语言表达的质量
4. 整体阅读体验

请给出详细的评价报告和改进建议。"""
    }
}

# 实例化设置
settings = Settings()