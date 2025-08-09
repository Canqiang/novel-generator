import openai
from typing import Dict, List
import tiktoken
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential
from redis_cache import RedisCache
import json
from datetime import datetime
from prompt_templates import PromptTemplates
from models import NovelRequest, NovelStatus


class NovelGenerator:
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo-16k"):
        self.api_key = api_key
        self.model = model
        openai.api_key = api_key
        self.encoding = tiktoken.encoding_for_model(model)
        self.templates = PromptTemplates()
        self.cache = RedisCache()

    async def generate_novel(self, request: NovelRequest, task_id: str) -> Dict:
        """主生成流程"""
        try:
            # 更新任务状态
            await self.update_task_status(task_id, NovelStatus.OUTLINING, 10)

            # 阶段1：生成大纲
            outline = await self.generate_outline(request)
            await self.update_task_status(task_id, NovelStatus.OUTLINING, 25)

            # 阶段2：生成章节大纲
            chapter_outlines = await self.generate_chapter_outlines(outline, request)
            await self.update_task_status(task_id, NovelStatus.WRITING, 40)

            # 阶段3：批量生成章节内容
            chapters = await self.generate_chapters_batch(chapter_outlines, outline)
            await self.update_task_status(task_id, NovelStatus.POLISHING, 80)

            # 阶段4：润色和优化
            final_chapters = await self.polish_chapters(chapters, outline)
            await self.update_task_status(task_id, NovelStatus.COMPLETED, 100)

            return {
                "title": outline["title"],
                "author_note": outline["author_note"],
                "outline": outline,
                "chapters": final_chapters,
                "metadata": {
                    "total_words": self.count_words(final_chapters),
                    "total_tokens": self.count_tokens(final_chapters),
                    "genre": request.genre,
                    "created_at": datetime.now().isoformat()
                }
            }

        except Exception as e:
            await self.update_task_status(task_id, NovelStatus.FAILED, error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def call_openai(self, messages: List[Dict], temperature: float = 0.8) -> str:
        """调用OpenAI API with retry"""
        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=2000
        )
        return response.choices[0].message.content

    async def generate_outline(self, request: NovelRequest) -> Dict:
        """生成故事大纲"""
        prompt = self.templates.get_outline_prompt(request)
        messages = [
            {"role": "system", "content": "你是一位专业的小说策划编辑，擅长构思精彩的故事。"},
            {"role": "user", "content": prompt}
        ]

        response = await self.call_openai(messages)
        return json.loads(response)

    async def generate_chapter_outlines(self, outline: Dict, request: NovelRequest) -> List[Dict]:
        """生成各章节大纲"""
        chapter_outlines = []

        for i in range(request.chapter_count):
            prompt = self.templates.get_chapter_outline_prompt(outline, i + 1)
            messages = [
                {"role": "system", "content": "你是一位专业的小说策划编辑。"},
                {"role": "user", "content": prompt}
            ]

            response = await self.call_openai(messages, temperature=0.7)
            chapter_outlines.append(json.loads(response))

        return chapter_outlines

    async def generate_chapters_batch(self, chapter_outlines: List[Dict], outline: Dict) -> List[Dict]:
        """批量生成章节（并发）"""

        async def generate_single_chapter(chapter_outline, chapter_num):
            # 使用滑动窗口保持上下文
            context = self.get_context_window(chapter_num, outline)
            prompt = self.templates.get_chapter_content_prompt(chapter_outline, context)

            messages = [
                {"role": "system", "content": "你是一位专业作家，文笔细腻，擅长人物刻画和情节推进。"},
                {"role": "user", "content": prompt}
            ]

            content = await self.call_openai(messages, temperature=0.85)
            return {
                "chapter_num": chapter_num,
                "title": chapter_outline["title"],
                "content": content
            }

        # 并发生成，但限制并发数避免rate limit
        tasks = []
        all_results = []
        for i, outline in enumerate(chapter_outlines):
            task = generate_single_chapter(outline, i + 1)
            tasks.append(task)

            # 每3个章节并发
            if (i + 1) % 3 == 0:
                batch_results = await asyncio.gather(*tasks)
                all_results.extend(batch_results)
                tasks = []

        # 处理剩余任务
        if tasks:
            batch_results = await asyncio.gather(*tasks)
            all_results.extend(batch_results)

        return sorted(all_results, key=lambda x: x["chapter_num"])

    async def polish_chapters(self, chapters: List[Dict], outline: Dict) -> List[Dict]:
        """润色章节"""
        polished = []

        for chapter in chapters:
            prompt = self.templates.get_polish_prompt(chapter["content"], outline)
            messages = [
                {"role": "system", "content": "你是一位资深编辑，负责提升文章质量。"},
                {"role": "user", "content": prompt}
            ]

            polished_content = await self.call_openai(messages, temperature=0.3)
            chapter["content"] = polished_content
            polished.append(chapter)

        return polished

    def get_previous_summary(self, chapter_num: int) -> str:
        """Placeholder for retrieving the summary of earlier chapters."""
        return ""

    def get_context_window(self, chapter_num: int, outline: Dict) -> Dict:
        """获取上下文窗口"""
        return {
            "characters": outline["characters"],
            "current_plot_stage": outline["plot_points"][chapter_num - 1] if chapter_num <= len(
                outline["plot_points"]) else "",
            "previous_summary": self.get_previous_summary(chapter_num)
        }

    def count_words(self, chapters: List[Dict]) -> int:
        """统计字数"""
        total = 0
        for chapter in chapters:
            total += len(chapter["content"].split())
        return total

    def count_tokens(self, chapters: List[Dict]) -> int:
        """统计tokens"""
        total = 0
        for chapter in chapters:
            tokens = self.encoding.encode(chapter["content"])
            total += len(tokens)
        return total

    async def update_task_status(self, task_id: str, status: NovelStatus,
                                 progress: int = 0, error: str = None):
        """更新任务状态到Redis"""
        try:
            status_value = status.value if hasattr(status, "value") else status
            self.cache.update_task_status(task_id, status_value, progress, error)
        except Exception as e:
            # 避免状态更新失败中断生成流程
            print(f"Failed to update status for {task_id}: {e}")
        # 这里应该更新到Redis或数据库
        pass
