# llm_providers.py - 多模型LLM支持
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, AsyncGenerator
import asyncio
import aiohttp
import openai
import anthropic
from dashscope import Generation as QwenGeneration
import json
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)


# ==================== 基础抽象类 ====================

class LLMProvider(ABC):
    """LLM提供商基础类"""

    def __init__(self, api_key: str, model: str = None):
        self.api_key = api_key
        self.model = model or self.default_model
        self.max_tokens = 2000
        self.temperature = 0.8

    @property
    @abstractmethod
    def default_model(self) -> str:
        """默认模型"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """提供商名称"""
        pass

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """生成文本"""
        pass

    @abstractmethod
    async def generate_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """计算Token数"""
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本"""
        pass


# ==================== OpenAI 提供商 ====================

class OpenAIProvider(LLMProvider):
    """OpenAI GPT模型提供商"""

    def __init__(self, api_key: str, model: str = None, base_url: str = None):
        super().__init__(api_key, model)
        openai.api_key = api_key
        if base_url:
            openai.api_base = base_url  # 支持代理

        # Token计数器
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    @property
    def default_model(self) -> str:
        return "gpt-3.5-turbo-16k"

    @property
    def name(self) -> str:
        return "OpenAI"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """生成文本"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await openai.ChatCompletion.acreate(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                top_p=kwargs.get('top_p', 0.9),
                frequency_penalty=kwargs.get('frequency_penalty', 0),
                presence_penalty=kwargs.get('presence_penalty', 0)
            )

            return response.choices[0].message.content

        except openai.error.RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            await asyncio.sleep(10)
            raise
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    async def generate_stream(self, prompt: str, system_prompt: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await openai.ChatCompletion.acreate(
            model=self.model,
            messages=messages,
            max_tokens=kwargs.get('max_tokens', self.max_tokens),
            temperature=kwargs.get('temperature', self.temperature),
            stream=True
        )

        async for chunk in response:
            if chunk.choices[0].delta.get('content'):
                yield chunk.choices[0].delta.content

    def count_tokens(self, text: str) -> int:
        """计算Token数"""
        return len(self.encoding.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（美元）"""
        pricing = {
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-32k": {"input": 0.06, "output": 0.12}
        }

        model_key = self.model
        for key in pricing.keys():
            if key in self.model:
                model_key = key
                break

        rates = pricing.get(model_key, pricing["gpt-3.5-turbo"])

        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return input_cost + output_cost


# ==================== Anthropic Claude 提供商 ====================

class AnthropicProvider(LLMProvider):
    """Anthropic Claude模型提供商"""

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model)
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def default_model(self) -> str:
        return "claude-3-sonnet-20240229"

    @property
    def name(self) -> str:
        return "Anthropic"

    async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """生成文本"""
        try:
            message = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                system=system_prompt if system_prompt else "You are a helpful assistant.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return message.content[0].text

        except Exception as e:
            logger.error(f"Claude generation error: {e}")
            raise

    async def generate_stream(self, prompt: str, system_prompt: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        stream = await self.client.messages.create(
            model=self.model,
            max_tokens=kwargs.get('max_tokens', self.max_tokens),
            temperature=kwargs.get('temperature', self.temperature),
            system=system_prompt if system_prompt else "You are a helpful assistant.",
            messages=[
                {"role": "user", "content": prompt}
            ],
            stream=True
        )

        async for chunk in stream:
            if chunk.type == "content_block_delta":
                yield chunk.delta.text

    def count_tokens(self, text: str) -> int:
        """估算Token数（Claude没有官方计数器）"""
        # 粗略估算：平均每个字符0.25个token
        return int(len(text) * 0.25)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（美元）"""
        pricing = {
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125}
        }

        rates = pricing.get(self.model, pricing["claude-3-sonnet-20240229"])

        input_cost = (input_tokens / 1000) * rates["input"]
        output_cost = (output_tokens / 1000) * rates["output"]

        return input_cost + output_cost


# ==================== 通义千问提供商 ====================

class QwenProvider(LLMProvider):
    """阿里通义千问模型提供商"""

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model)

    @property
    def default_model(self) -> str:
        return "qwen-turbo"

    @property
    def name(self) -> str:
        return "Qwen"

    async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """生成文本"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = QwenGeneration.call(
                model=self.model,
                messages=messages,
                api_key=self.api_key,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                top_p=kwargs.get('top_p', 0.9)
            )

            return response.output.text

        except Exception as e:
            logger.error(f"Qwen generation error: {e}")
            raise

    async def generate_stream(self, prompt: str, system_prompt: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        responses = QwenGeneration.call(
            model=self.model,
            messages=messages,
            api_key=self.api_key,
            max_tokens=kwargs.get('max_tokens', self.max_tokens),
            temperature=kwargs.get('temperature', self.temperature),
            stream=True
        )

        for response in responses:
            if response.output and response.output.text:
                yield response.output.text

    def count_tokens(self, text: str) -> int:
        """估算Token数"""
        # 中文大约1.5个字符一个token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（人民币）"""
        pricing = {
            "qwen-turbo": {"input": 0.008, "output": 0.008},
            "qwen-plus": {"input": 0.02, "output": 0.02},
            "qwen-max": {"input": 0.12, "output": 0.12}
        }

        rates = pricing.get(self.model, pricing["qwen-turbo"])

        # 转换为美元（假设汇率7.2）
        rmb_cost = ((input_tokens + output_tokens) / 1000) * rates["input"]
        return rmb_cost / 7.2


# ==================== 月之暗面 Moonshot 提供商 ====================

class MoonshotProvider(LLMProvider):
    """月之暗面Kimi模型提供商"""

    def __init__(self, api_key: str, model: str = None):
        super().__init__(api_key, model)
        self.base_url = "https://api.moonshot.cn/v1"

    @property
    def default_model(self) -> str:
        return "moonshot-v1-8k"

    @property
    def name(self) -> str:
        return "Moonshot"

    async def generate(self, prompt: str, system_prompt: str = None, **kwargs) -> str:
        """生成文本"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "temperature": kwargs.get('temperature', self.temperature)
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
            ) as response:
                result = await response.json()
                return result["choices"][0]["message"]["content"]

    async def generate_stream(self, prompt: str, system_prompt: str = None, **kwargs) -> AsyncGenerator[str, None]:
        """流式生成"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        data = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get('max_tokens', self.max_tokens),
            "temperature": kwargs.get('temperature', self.temperature),
            "stream": True
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data
            ) as response:
                async for line in response.content:
                    if line:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith("data: "):
                            if line_text == "data: [DONE]":
                                break
                            try:
                                chunk = json.loads(line_text[6:])
                                if chunk["choices"][0]["delta"].get("content"):
                                    yield chunk["choices"][0]["delta"]["content"]
                            except json.JSONDecodeError:
                                continue

    def count_tokens(self, text: str) -> int:
        """估算Token数"""
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len(text) - chinese_chars
        return int(chinese_chars / 1.5 + english_chars / 4)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """估算成本（人民币转美元）"""
        pricing = {
            "moonshot-v1-8k": 0.012,
            "moonshot-v1-32k": 0.024,
            "moonshot-v1-128k": 0.060
        }

        rate = pricing.get(self.model, 0.012)
        rmb_cost = ((input_tokens + output_tokens) / 1000) * rate
        return rmb_cost / 7.2


# ==================== 多模型管理器 ====================

class MultiModelManager:
    """多模型管理器"""

    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self.default_provider = None

    def register_provider(self, name: str, provider: LLMProvider, is_default: bool = False):
        """注册提供商"""
        self.providers[name] = provider
        if is_default or not self.default_provider:
            self.default_provider = name
        logger.info(f"Registered provider: {name}")

    def get_provider(self, name: str = None) -> LLMProvider:
        """获取提供商"""
        if name:
            return self.providers.get(name)
        return self.providers.get(self.default_provider)

    async def generate_with_fallback(self, prompt: str, providers: List[str] = None, **kwargs) -> str:
        """带失败回退的生成"""
        if not providers:
            providers = list(self.providers.keys())

        last_error = None
        for provider_name in providers:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            try:
                logger.info(f"Trying provider: {provider_name}")
                result = await provider.generate(prompt, **kwargs)
                logger.info(f"Success with provider: {provider_name}")
                return result
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                last_error = e
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")

    async def generate_parallel(self, prompt: str, providers: List[str] = None, **kwargs) -> Dict[str, str]:
        """并行生成（用于对比）"""
        if not providers:
            providers = list(self.providers.keys())[:3]  # 最多3个

        tasks = []
        for provider_name in providers:
            provider = self.providers.get(provider_name)
            if provider:
                task = asyncio.create_task(
                    self._generate_with_provider(provider_name, provider, prompt, **kwargs)
                )
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for provider_name, result in zip(providers, results):
            if isinstance(result, Exception):
                output[provider_name] = f"Error: {str(result)}"
            else:
                output[provider_name] = result

        return output

    async def _generate_with_provider(self, name: str, provider: LLMProvider,
                                      prompt: str, **kwargs) -> str:
        """使用特定提供商生成"""
        try:
            return await provider.generate(prompt, **kwargs)
        except Exception as e:
            logger.error(f"Provider {name} error: {e}")
            raise

    def estimate_total_cost(self, text: str, output_length: int = 2000) -> Dict[str, float]:
        """估算所有提供商的成本"""
        costs = {}
        for name, provider in self.providers.items():
            input_tokens = provider.count_tokens(text)
            output_tokens = output_length  # 估算
            cost = provider.estimate_cost(input_tokens, output_tokens)
            costs[name] = round(cost, 4)

        return costs


# ==================== 智能路由器 ====================

class IntelligentRouter:
    """基于任务类型智能选择模型"""

    def __init__(self, manager: MultiModelManager):
        self.manager = manager

        # 任务类型到模型的映射
        self.task_routing = {
            "outline": ["claude", "gpt-4"],  # 大纲需要强逻辑
            "creative": ["claude", "gpt-3.5-turbo"],  # 创意写作
            "dialogue": ["gpt-3.5-turbo", "qwen"],  # 对话生成
            "polish": ["claude", "gpt-4"],  # 润色需要高质量
            "translate": ["gpt-3.5-turbo", "qwen"],  # 翻译
            "summary": ["gpt-3.5-turbo", "qwen"],  # 摘要
        }

    async def route_request(self, task_type: str, prompt: str, **kwargs) -> str:
        """根据任务类型路由请求"""
        providers = self.task_routing.get(task_type, ["gpt-3.5-turbo"])

        # 根据内容长度调整
        if len(prompt) > 10000:
            # 长文本优先使用支持长上下文的模型
            providers = ["claude", "moonshot-v1-128k"]

        return await self.manager.generate_with_fallback(prompt, providers, **kwargs)


# ==================== 使用示例 ====================

async def main():
    # 初始化管理器
    manager = MultiModelManager()

    # 注册提供商
    if openai_key := os.getenv("OPENAI_API_KEY"):
        manager.register_provider(
            "gpt-3.5",
            OpenAIProvider(openai_key, model="gpt-3.5-turbo-16k"),
            is_default=True
        )

    if claude_key := os.getenv("ANTHROPIC_API_KEY"):
        manager.register_provider(
            "claude",
            AnthropicProvider(claude_key)
        )

    if qwen_key := os.getenv("DASHSCOPE_API_KEY"):
        manager.register_provider(
            "qwen",
            QwenProvider(qwen_key)
        )

    if moonshot_key := os.getenv("MOONSHOT_API_KEY"):
        manager.register_provider(
            "moonshot",
            MoonshotProvider(moonshot_key)
        )

    # 测试生成
    prompt = "写一个100字的科幻故事开头"

    # 单个生成
    result = await manager.generate_with_fallback(prompt)
    print("Generated:", result[:100])

    # 并行对比
    comparison = await manager.generate_parallel(prompt)
    for provider, content in comparison.items():
        print(f"\n{provider}:")
        print(content[:200])

    # 成本估算
    costs = manager.estimate_total_cost(prompt)
    print("\nEstimated costs:", costs)

    # 智能路由
    router = IntelligentRouter(manager)
    creative_result = await router.route_request("creative", prompt)
    print("\nRouted result:", creative_result[:100])


if __name__ == "__main__":
    import os

    asyncio.run(main())