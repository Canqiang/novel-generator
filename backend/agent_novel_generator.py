import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings, AGENT_ROLES, PROMPT_TEMPLATES, NOVEL_CONFIG
from models import (
    NovelRequest, NovelResult, NovelOutline, Chapter, ChapterOutline,
    AgentRole, AgentMessage, AgentResponse, NovelStatus, NovelTask
)
from redis_cache import RedisCache

logger = logging.getLogger(__name__)


class AIAgent:
    """AI Agent基类"""

    def __init__(self, role: AgentRole, api_key: str, base_url: str = None):
        self.role = role
        self.api_key = api_key
        self.base_url = base_url or settings.OPENAI_BASE_URL
        self.model = settings.OPENAI_MODEL
        self.temperature = settings.OPENAI_TEMPERATURE
        self.max_tokens = settings.OPENAI_MAX_TOKENS

        # 设置OpenAI客户端
        openai.api_key = api_key
        if base_url:
            openai.api_base = base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def call_llm(self, messages: List[Dict], temperature: float = None) -> str:
        """调用LLM API"""
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM API调用失败 ({self.role}): {e}")
            raise

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """处理任务并返回响应"""
        raise NotImplementedError

    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        return PROMPT_TEMPLATES["system_prompts"].get(self.role.value, "")


class PlannerAgent(AIAgent):
    """策划师Agent - 负责故事策划和大纲设计"""

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """生成故事大纲"""
        request: NovelRequest = context["request"]

        # 构建策划提示词
        prompt = self._build_planning_prompt(request)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            response_content = await self.call_llm(messages, temperature=0.7)
            outline_data = json.loads(response_content)

            # 验证和补充大纲数据
            outline = self._validate_and_enhance_outline(outline_data, request)

            return AgentResponse(
                agent_role=self.role,
                content=json.dumps(outline.dict(), ensure_ascii=False, indent=2),
                quality_score=self._evaluate_outline_quality(outline),
                suggestions=self._generate_planning_suggestions(outline),
                next_action="begin_writing",
                metadata={"outline_created": True, "chapter_count": len(outline.chapter_outlines)}
            )

        except json.JSONDecodeError as e:
            logger.error(f"大纲解析失败: {e}")
            # 重试或返回错误
            raise Exception(f"大纲格式错误: {e}")
        except Exception as e:
            logger.error(f"策划过程出错: {e}")
            raise

    def _build_planning_prompt(self, request: NovelRequest) -> str:
        """构建策划提示词"""
        genre_info = NOVEL_CONFIG["genres"].get(request.genre.value if request.genre else "urban_romance", {})

        prompt = f"""
请为以下需求创作一个完整的小说大纲：

**创作需求：**
- 主题：{request.theme}
- 类型：{request.genre.value if request.genre else "自动判断"} - {genre_info.get("description", "")}
- 风格：{request.style.value}
- 目标字数：{request.word_count}字
- 章节数：{request.chapter_count}章
- 目标读者：{request.target_audience}

**类型特色：**
{json.dumps(genre_info.get("style_prompts", {}), ensure_ascii=False, indent=2)}

请生成严格的JSON格式大纲，包含以下结构：
{{
    "title": "吸引人的标题",
    "subtitle": "副标题（可选）",
    "author_note": "作者的话（100字内，{request.style.value}）",
    "one_line_pitch": "一句话介绍这个故事",
    "genre": "具体细分类型",
    "theme": "核心主题",
    "tone": "整体基调",

    "characters": {{
        "protagonist": {{
            "name": "主角姓名",
            "age": 年龄,
            "occupation": "职业",
            "personality": "性格特点",
            "motivation": "核心动机",
            "arc": "角色成长弧线",
            "background": "背景故事"
        }},
        "supporting": [
            {{
                "name": "配角姓名",
                "role": "角色定位",
                "relationship": "与主角关系",
                "personality": "性格特点",
                "importance": "重要程度(1-5)"
            }}
        ]
    }},

    "world_setting": {{
        "time": "时间背景",
        "location": "主要地点",
        "atmosphere": "氛围描述",
        "special_rules": "特殊设定或规则",
        "social_context": "社会背景"
    }},

    "plot_structure": {{
        "hook": "开篇钩子",
        "inciting_incident": "激励事件",
        "plot_points": ["情节点1", "情节点2", "情节点3"],
        "climax": "高潮事件",
        "resolution": "结局"
    }},

    "chapter_outlines": [
        {{
            "chapter_num": 1,
            "title": "第1章标题",
            "summary": "章节概要",
            "key_events": ["事件1", "事件2"],
            "characters_involved": ["角色1", "角色2"],
            "mood": "章节氛围",
            "target_word_count": {request.word_count // request.chapter_count}
        }}
        // ... 共{request.chapter_count}章
    ],

    "themes_to_explore": ["主题1", "主题2", "主题3"],
    "key_symbols": ["象征1", "象征2"],
    "target_readers": "{request.target_audience}"
}}

**创作要求：**
1. 故事要有强烈的冲突和张力
2. 人物要立体可信，有成长弧线
3. 适合{request.target_audience}的阅读习惯
4. 每章都要有明确的目标和进展
5. 整体结构要完整且引人入胜

请确保返回的是完整、有效的JSON格式。
"""
        return prompt

    def _validate_and_enhance_outline(self, outline_data: Dict, request: NovelRequest) -> NovelOutline:
        """验证和增强大纲数据"""
        # 确保必要字段存在
        required_fields = ["title", "author_note", "characters", "chapter_outlines"]
        for field in required_fields:
            if field not in outline_data:
                raise ValueError(f"大纲缺少必要字段: {field}")

        # 转换章节大纲格式
        chapter_outlines = []
        for i, chapter_data in enumerate(outline_data.get("chapter_outlines", [])):
            chapter_outlines.append(ChapterOutline(
                chapter_num=i + 1,
                title=chapter_data.get("title", f"第{i + 1}章"),
                summary=chapter_data.get("summary", ""),
                key_events=chapter_data.get("key_events", []),
                characters_involved=chapter_data.get("characters_involved", []),
                mood=chapter_data.get("mood", "neutral"),
                target_word_count=chapter_data.get("target_word_count", request.word_count // request.chapter_count)
            ))

        # 创建完整的大纲对象
        outline = NovelOutline(
            title=outline_data["title"],
            subtitle=outline_data.get("subtitle"),
            author_note=outline_data["author_note"],
            one_line_pitch=outline_data.get("one_line_pitch", ""),
            genre=outline_data.get("genre", request.genre.value if request.genre else ""),
            theme=outline_data.get("theme", request.theme),
            tone=outline_data.get("tone", ""),
            characters=outline_data["characters"],
            world_setting=outline_data.get("world_setting", {}),
            plot_structure=outline_data.get("plot_structure", {}),
            plot_points=outline_data.get("plot_points", []),
            chapter_outlines=chapter_outlines,
            themes_to_explore=outline_data.get("themes_to_explore", []),
            key_symbols=outline_data.get("key_symbols", []),
            target_readers=outline_data.get("target_readers", request.target_audience)
        )

        return outline

    def _evaluate_outline_quality(self, outline: NovelOutline) -> float:
        """评估大纲质量"""
        score = 0.0
        total_criteria = 0

        # 检查完整性
        if outline.title and len(outline.title) > 5:
            score += 1
        total_criteria += 1

        if outline.characters and "protagonist" in outline.characters:
            score += 1
        total_criteria += 1

        if len(outline.chapter_outlines) >= 3:
            score += 1
        total_criteria += 1

        if outline.plot_structure and len(outline.plot_structure) >= 3:
            score += 1
        total_criteria += 1

        if outline.themes_to_explore and len(outline.themes_to_explore) >= 2:
            score += 1
        total_criteria += 1

        return score / total_criteria if total_criteria > 0 else 0.0

    def _generate_planning_suggestions(self, outline: NovelOutline) -> List[str]:
        """生成策划建议"""
        suggestions = []

        if not outline.subtitle:
            suggestions.append("考虑添加一个副标题来更好地概括故事")

        if len(outline.characters.get("supporting", [])) < 2:
            suggestions.append("建议增加更多配角来丰富故事层次")

        if len(outline.themes_to_explore) < 3:
            suggestions.append("可以探索更多主题深度")

        return suggestions


class WriterAgent(AIAgent):
    """创作者Agent - 负责具体内容创作"""

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """创作章节内容"""
        outline: NovelOutline = context["outline"]
        chapter_num: int = context["chapter_num"]
        previous_chapters: List[Chapter] = context.get("previous_chapters", [])

        if chapter_num > len(outline.chapter_outlines):
            raise ValueError(f"章节编号超出范围: {chapter_num}")

        chapter_outline = outline.chapter_outlines[chapter_num - 1]

        # 构建创作提示词
        prompt = self._build_writing_prompt(outline, chapter_outline, previous_chapters)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            content = await self.call_llm(messages, temperature=0.85)

            # 创建章节对象
            chapter = Chapter(
                chapter_num=chapter_num,
                title=chapter_outline.title,
                content=content,
                word_count=len(content.split())
            )

            # 评估内容质量
            quality_score = self._evaluate_content_quality(chapter, chapter_outline)

            return AgentResponse(
                agent_role=self.role,
                content=json.dumps(chapter.dict(), ensure_ascii=False, indent=2),
                quality_score=quality_score,
                suggestions=self._generate_writing_suggestions(chapter, chapter_outline),
                next_action="review_content",
                metadata={
                    "chapter_num": chapter_num,
                    "word_count": chapter.word_count,
                    "target_word_count": chapter_outline.target_word_count
                }
            )

        except Exception as e:
            logger.error(f"创作过程出错: {e}")
            raise

    def _build_writing_prompt(self, outline: NovelOutline, chapter_outline: ChapterOutline,
                              previous_chapters: List[Chapter]) -> str:
        """构建创作提示词"""
        # 获取前情提要
        previous_summary = self._generate_previous_summary(previous_chapters)

        prompt = f"""
请根据以下信息创作第{chapter_outline.chapter_num}章的内容：

**故事概况：**
- 标题：{outline.title}
- 主题：{outline.theme}
- 基调：{outline.tone}
- 一句话概括：{outline.one_line_pitch}

**人物设定：**
{json.dumps(outline.characters, ensure_ascii=False, indent=2)}

**世界观设定：**
{json.dumps(outline.world_setting, ensure_ascii=False, indent=2)}

**本章大纲：**
- 章节：{chapter_outline.title}
- 概要：{chapter_outline.summary}
- 关键事件：{', '.join(chapter_outline.key_events)}
- 涉及角色：{', '.join(chapter_outline.characters_involved)}
- 氛围：{chapter_outline.mood}
- 目标字数：{chapter_outline.target_word_count}字

**前情回顾：**
{previous_summary}

**创作要求：**
1. 字数控制在{chapter_outline.target_word_count - 200}到{chapter_outline.target_word_count + 200}字之间
2. 保持人物性格的一致性
3. 推进主要情节，实现章节目标
4. 使用丰富的对话推进剧情（对话比例30-40%）
5. 加入感官细节，增强画面感
6. 保持{outline.tone}的整体基调
7. 如果不是最后一章，要在结尾留下悬念

**风格特点：**
- 语言现代流畅，适合现代读者
- 避免过度修饰，保持可读性
- 适当融入思考性内容
- 节奏张弛有度

请直接输出章节内容，不要添加任何额外的解释或标记。
"""
        return prompt

    def _generate_previous_summary(self, previous_chapters: List[Chapter]) -> str:
        """生成前情提要"""
        if not previous_chapters:
            return "这是故事的开端。"

        # 取最近的几章进行总结
        recent_chapters = previous_chapters[-2:] if len(previous_chapters) > 2 else previous_chapters

        summary_parts = []
        for chapter in recent_chapters:
            # 简化章节内容为摘要
            content_excerpt = chapter.content[:200] + "..." if len(chapter.content) > 200 else chapter.content
            summary_parts.append(f"{chapter.title}：{content_excerpt}")

        return "\n".join(summary_parts)

    def _evaluate_content_quality(self, chapter: Chapter, chapter_outline: ChapterOutline) -> float:
        """评估内容质量"""
        score = 0.0
        total_criteria = 0

        # 字数达标检查
        target_word_count = chapter_outline.target_word_count
        word_diff = abs(chapter.word_count - target_word_count) / target_word_count
        if word_diff <= 0.2:  # 20%误差内
            score += 1
        total_criteria += 1

        # 对话比例检查（简单估算）
        dialogue_count = chapter.content.count('"') + chapter.content.count('"') + chapter.content.count('"')
        if dialogue_count >= 6:  # 至少3轮对话
            score += 1
        total_criteria += 1

        # 段落结构检查
        paragraphs = [p.strip() for p in chapter.content.split('\n') if p.strip()]
        if len(paragraphs) >= 5:  # 至少5个段落
            score += 1
        total_criteria += 1

        # 内容长度合理性
        if len(chapter.content) > 500:  # 不能太短
            score += 1
        total_criteria += 1

        return score / total_criteria if total_criteria > 0 else 0.0

    def _generate_writing_suggestions(self, chapter: Chapter, chapter_outline: ChapterOutline) -> List[str]:
        """生成创作建议"""
        suggestions = []

        # 检查字数
        if chapter.word_count < chapter_outline.target_word_count * 0.8:
            suggestions.append(f"内容偏短，建议扩充至{chapter_outline.target_word_count}字左右")
        elif chapter.word_count > chapter_outline.target_word_count * 1.2:
            suggestions.append(f"内容偏长，建议精简至{chapter_outline.target_word_count}字左右")

        # 检查对话
        dialogue_count = chapter.content.count('"')
        if dialogue_count < 4:
            suggestions.append("建议增加更多对话来推进情节")

        # 检查结构
        paragraphs = [p.strip() for p in chapter.content.split('\n') if p.strip()]
        if len(paragraphs) < 5:
            suggestions.append("建议调整段落结构，增加层次感")

        return suggestions


class EditorAgent(AIAgent):
    """编辑Agent - 负责内容审核和优化"""

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """编辑和优化内容"""
        chapter: Chapter = context["chapter"]
        outline: NovelOutline = context["outline"]
        previous_chapters: List[Chapter] = context.get("previous_chapters", [])

        # 构建编辑提示词
        prompt = self._build_editing_prompt(chapter, outline, previous_chapters)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            edited_content = await self.call_llm(messages, temperature=0.3)

            # 更新章节内容
            edited_chapter = Chapter(
                chapter_num=chapter.chapter_num,
                title=chapter.title,
                content=edited_content,
                word_count=len(edited_content.split()),
                editor_notes="已优化语言表达和结构"
            )

            # 评估编辑质量
            quality_score = self._evaluate_editing_quality(edited_chapter, chapter)

            return AgentResponse(
                agent_role=self.role,
                content=json.dumps(edited_chapter.dict(), ensure_ascii=False, indent=2),
                quality_score=quality_score,
                suggestions=self._generate_editing_suggestions(edited_chapter, chapter),
                next_action="final_review",
                metadata={
                    "original_word_count": chapter.word_count,
                    "edited_word_count": edited_chapter.word_count,
                    "improvement_score": quality_score
                }
            )

        except Exception as e:
            logger.error(f"编辑过程出错: {e}")
            raise

    def _build_editing_prompt(self, chapter: Chapter, outline: NovelOutline,
                              previous_chapters: List[Chapter]) -> str:
        """构建编辑提示词"""
        prompt = f"""
请对以下章节内容进行编辑优化：

**章节信息：**
- 章节：{chapter.title}
- 当前字数：{chapter.word_count}
- 在整体故事中的位置：第{chapter.chapter_num}章，共{len(outline.chapter_outlines)}章

**故事背景：**
- 故事主题：{outline.theme}
- 故事基调：{outline.tone}
- 主要人物：{', '.join([char['name'] for char in [outline.characters.get('protagonist', {})] + outline.characters.get('supporting', []) if 'name' in char])}

**原始内容：**
{chapter.content}

**编辑要求：**
1. **语言优化**：
   - 删除冗余表达和重复词汇
   - 优化句式结构，提高流畅度
   - 增强画面感和代入感
   - 确保语言风格统一

2. **逻辑检查**：
   - 确保情节逻辑通顺
   - 检查时间线的一致性
   - 保持人物性格的连贯性
   - 与前文的衔接自然

3. **对话优化**：
   - 使对话更自然生动
   - 确保符合人物性格
   - 通过对话推进情节

4. **细节增强**：
   - 适当添加感官细节
   - 强化氛围营造
   - 优化场景转换

5. **可读性提升**：
   - 保持现代读者的阅读习惯
   - 控制段落长度
   - 确保节奏适宜

请直接输出优化后的完整内容，不要添加解释或标记。
"""
        return prompt

    def _evaluate_editing_quality(self, edited_chapter: Chapter, original_chapter: Chapter) -> float:
        """评估编辑质量"""
        score = 0.0
        total_criteria = 0

        # 内容长度变化合理性
        word_change_ratio = abs(edited_chapter.word_count - original_chapter.word_count) / original_chapter.word_count
        if word_change_ratio <= 0.15:  # 变化不超过15%
            score += 1
        total_criteria += 1

        # 结构改善检查
        original_paragraphs = len([p for p in original_chapter.content.split('\n') if p.strip()])
        edited_paragraphs = len([p for p in edited_chapter.content.split('\n') if p.strip()])

        if edited_paragraphs >= original_paragraphs:  # 结构保持或改善
            score += 1
        total_criteria += 1

        # 内容完整性检查
        if len(edited_chapter.content) >= len(original_chapter.content) * 0.9:
            score += 1
        total_criteria += 1

        return score / total_criteria if total_criteria > 0 else 0.0

    def _generate_editing_suggestions(self, edited_chapter: Chapter, original_chapter: Chapter) -> List[str]:
        """生成编辑建议"""
        suggestions = []

        word_change = edited_chapter.word_count - original_chapter.word_count
        if abs(word_change) > original_chapter.word_count * 0.1:
            if word_change > 0:
                suggestions.append(f"内容增加了{word_change}字，请确认是否合适")
            else:
                suggestions.append(f"内容减少了{abs(word_change)}字，确保信息完整")

        if edited_chapter.word_count < 800:
            suggestions.append("章节内容偏短，可考虑适当扩充")

        return suggestions


class ReviewerAgent(AIAgent):
    """评审者Agent - 负责质量评估和反馈"""

    async def process(self, context: Dict[str, Any]) -> AgentResponse:
        """评审内容质量"""
        if "chapter" in context:
            return await self._review_chapter(context)
        elif "outline" in context:
            return await self._review_outline(context)
        else:
            raise ValueError("需要评审的内容类型不明确")

    async def _review_chapter(self, context: Dict[str, Any]) -> AgentResponse:
        """评审章节内容"""
        chapter: Chapter = context["chapter"]
        outline: NovelOutline = context["outline"]
        chapter_outline = outline.chapter_outlines[chapter.chapter_num - 1]

        # 构建评审提示词
        prompt = self._build_chapter_review_prompt(chapter, chapter_outline, outline)

        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        try:
            review_result = await self.call_llm(messages, temperature=0.2)
            review_data = json.loads(review_result)

            # 计算综合质量分数
            quality_score = self._calculate_quality_score(review_data)

            return AgentResponse(
                agent_role=self.role,
                content=json.dumps(review_data, ensure_ascii=False, indent=2),
                quality_score=quality_score,
                suggestions=review_data.get("suggestions", []),
                next_action="accept" if quality_score >= 0.7 else "revise",
                metadata={
                    "review_type": "chapter",
                    "chapter_num": chapter.chapter_num,
                    "detailed_scores": review_data.get("scores", {})
                }
            )

        except json.JSONDecodeError:
            # 如果无法解析JSON，返回基础评审
            return AgentResponse(
                agent_role=self.role,
                content=review_result,
                quality_score=0.6,
                suggestions=["请重新检查内容格式"],
                next_action="revise"
            )

    def _build_chapter_review_prompt(self, chapter: Chapter, chapter_outline: ChapterOutline,
                                     outline: NovelOutline) -> str:
        """构建章节评审提示词"""
        prompt = f"""
请对以下章节内容进行专业评审：

**章节目标：**
- 标题：{chapter_outline.title}
- 概要：{chapter_outline.summary}
- 关键事件：{', '.join(chapter_outline.key_events)}
- 目标字数：{chapter_outline.target_word_count}
- 预期氛围：{chapter_outline.mood}

**实际内容：**
- 标题：{chapter.title}
- 实际字数：{chapter.word_count}
- 内容：{chapter.content[:500]}...（内容较长，已截取开头）

**评审维度：**
请从以下几个维度评分（1-5分）并给出具体建议：

1. **内容完整性**：是否完整实现了章节目标
2. **情节推进**：是否有效推进了整体故事
3. **人物刻画**：人物是否生动可信
4. **语言质量**：文字表达是否流畅优美
5. **节奏把控**：情节节奏是否适宜
6. **细节描写**：场景和氛围描写是否生动
7. **逻辑一致性**：是否与前文保持一致
8. **可读性**：是否符合目标读者口味

请返回以下JSON格式的评审报告：
{{
    "overall_score": 总体评分(1-5),
    "scores": {{
        "completeness": 完整性评分,
        "plot_progression": 情节推进评分,
        "character_development": 人物刻画评分,
        "language_quality": 语言质量评分,
        "pacing": 节奏把控评分,
        "details": 细节描写评分,
        "consistency": 逻辑一致性评分,
        "readability": 可读性评分
    }},
    "strengths": ["优点1", "优点2", "优点3"],
    "weaknesses": ["不足1", "不足2"],
    "suggestions": ["改进建议1", "改进建议2", "改进建议3"],
    "word_count_assessment": "字数评价",
    "recommendation": "accept/revise/rewrite"
}}
"""
        return prompt

    def _calculate_quality_score(self, review_data: Dict) -> float:
        """计算质量分数"""
        if "scores" in review_data:
            scores = review_data["scores"]
            total_score = sum(scores.values())
            max_score = len(scores) * 5
            return total_score / max_score if max_score > 0 else 0.0
        elif "overall_score" in review_data:
            return review_data["overall_score"] / 5.0
        else:
            return 0.6  # 默认分数


class AgentNovelGenerator:
    """基于Agent协作的小说生成器"""

    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url
        self.cache = RedisCache()

        # 初始化各个Agent
        self.planner = PlannerAgent(AgentRole.PLANNER, api_key, base_url)
        self.writer = WriterAgent(AgentRole.WRITER, api_key, base_url)
        self.editor = EditorAgent(AgentRole.EDITOR, api_key, base_url)
        self.reviewer = ReviewerAgent(AgentRole.REVIEWER, api_key, base_url)

        logger.info("Agent小说生成器初始化完成")

    async def generate_novel(self, request: NovelRequest, task_id: str) -> NovelResult:
        """主生成流程"""
        try:
            # 记录开始时间
            start_time = datetime.now()
            collaboration_log = []

            # 阶段1：策划大纲
            await self._update_task_status(task_id, NovelStatus.PLANNING, 10, "策划师正在设计故事大纲...")

            outline_response = await self.planner.process({"request": request})
            outline = NovelOutline.parse_raw(outline_response.content)

            collaboration_log.append(AgentMessage(
                role=AgentRole.PLANNER,
                content=f"完成故事大纲设计，质量评分：{outline_response.quality_score}"
            ))

            # 大纲质量检查
            if outline_response.quality_score < 0.6:
                await self._update_task_status(task_id, NovelStatus.PLANNING, 15, "大纲质量不足，重新策划...")
                # 可以重试或调整

            await self._update_task_status(task_id, NovelStatus.WRITING, 25, "开始创作章节内容...")

            # 阶段2：逐章创作
            chapters = []
            for chapter_num in range(1, len(outline.chapter_outlines) + 1):
                progress = 25 + (chapter_num - 1) * 40 // len(outline.chapter_outlines)
                await self._update_task_status(
                    task_id, NovelStatus.WRITING, progress,
                    f"创作第{chapter_num}章：{outline.chapter_outlines[chapter_num - 1].title}"
                )

                # 创作章节
                chapter = await self._create_chapter_with_collaboration(
                    outline, chapter_num, chapters, collaboration_log
                )
                chapters.append(chapter)

            await self._update_task_status(task_id, NovelStatus.REVIEWING, 80, "进行最终审核...")

            # 阶段3：最终审核和优化
            final_chapters = await self._final_review_and_polish(chapters, outline, collaboration_log)

            # 生成最终结果
            generation_stats = {
                "total_time": (datetime.now() - start_time).total_seconds(),
                "total_words": sum(ch.word_count for ch in final_chapters),
                "average_chapter_words": sum(ch.word_count for ch in final_chapters) // len(final_chapters),
                "collaboration_messages": len(collaboration_log)
            }

            result = NovelResult(
                title=outline.title,
                author_note=outline.author_note,
                outline=outline,
                chapters=final_chapters,
                metadata={
                    "genre": request.genre.value if request.genre else "auto",
                    "style": request.style.value,
                    "created_at": datetime.now().isoformat(),
                    "agent_collaboration": True
                },
                generation_stats=generation_stats,
                collaboration_log=collaboration_log
            )

            await self._update_task_status(task_id, NovelStatus.COMPLETED, 100, "小说创作完成!")

            return result

        except Exception as e:
            logger.error(f"小说生成失败: {e}")
            await self._update_task_status(task_id, NovelStatus.FAILED, error=str(e))
            raise

    async def _create_chapter_with_collaboration(self, outline: NovelOutline, chapter_num: int,
                                                 previous_chapters: List[Chapter],
                                                 collaboration_log: List[AgentMessage]) -> Chapter:
        """协作创作单个章节"""
        max_iterations = settings.AGENT_MAX_ITERATIONS

        for iteration in range(max_iterations):
            # 创作内容
            writer_context = {
                "outline": outline,
                "chapter_num": chapter_num,
                "previous_chapters": previous_chapters
            }
            writer_response = await self.writer.process(writer_context)
            chapter = Chapter.parse_raw(writer_response.content)

            collaboration_log.append(AgentMessage(
                role=AgentRole.WRITER,
                content=f"第{chapter_num}章创作完成（迭代{iteration + 1}），质量评分：{writer_response.quality_score}"
            ))

            # 如果质量足够好，直接使用
            if writer_response.quality_score >= settings.AGENT_REVIEW_THRESHOLD:
                break

            # 否则进行编辑优化
            if iteration < max_iterations - 1:
                editor_context = {
                    "chapter": chapter,
                    "outline": outline,
                    "previous_chapters": previous_chapters
                }
                editor_response = await self.editor.process(editor_context)
                chapter = Chapter.parse_raw(editor_response.content)

                collaboration_log.append(AgentMessage(
                    role=AgentRole.EDITOR,
                    content=f"第{chapter_num}章编辑优化完成（迭代{iteration + 1}），改进评分：{editor_response.quality_score}"
                ))

        return chapter

    async def _final_review_and_polish(self, chapters: List[Chapter], outline: NovelOutline,
                                       collaboration_log: List[AgentMessage]) -> List[Chapter]:
        """最终审核和润色"""
        polished_chapters = []

        for chapter in chapters:
            # 最终评审
            review_context = {
                "chapter": chapter,
                "outline": outline
            }
            review_response = await self.reviewer.process(review_context)

            collaboration_log.append(AgentMessage(
                role=AgentRole.REVIEWER,
                content=f"第{chapter.chapter_num}章最终评审完成，质量评分：{review_response.quality_score}"
            ))

            # 如果需要进一步优化
            if review_response.quality_score < 0.8 and review_response.next_action == "revise":
                editor_context = {
                    "chapter": chapter,
                    "outline": outline,
                    "previous_chapters": polished_chapters
                }
                editor_response = await self.editor.process(editor_context)
                final_chapter = Chapter.parse_raw(editor_response.content)
                polished_chapters.append(final_chapter)
            else:
                polished_chapters.append(chapter)

        return polished_chapters

    async def _update_task_status(self, task_id: str, status: NovelStatus,
                                  progress: int = 0, message: str = None, error: str = None):
        """更新任务状态"""
        try:
            self.cache.update_task_status(task_id, status.value, progress, error)
            if message:
                # 更新当前阶段信息
                task_data = self.cache.get_task(task_id) or {}
                task_data["current_stage"] = message
                self.cache.set_task(task_id, task_data)
        except Exception as e:
            logger.warning(f"状态更新失败: {e}")  # 不中断主流程