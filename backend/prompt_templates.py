from typing import Dict, List
import json
from models import NovelRequest, ChapterOutline, NovelOutline, Chapter
from config import NOVEL_CONFIG, AGENT_ROLES


class PromptTemplates:
    """提示词模板管理类"""

    def __init__(self):
        self.genre_config = NOVEL_CONFIG["genres"]
        self.style_config = NOVEL_CONFIG["writing_styles"]
        self.agent_config = AGENT_ROLES

    def get_outline_prompt(self, request: NovelRequest) -> str:
        """获取大纲生成提示词"""
        genre_info = self.genre_config.get(request.genre.value if request.genre else "urban_romance", {})
        style_info = self.style_config.get(request.style.value, {})

        prompt = f"""
你是一位资深的小说策划编辑，具有丰富的故事创作和结构设计经验。请为以下需求创作一个完整的中篇小说大纲。

**创作需求分析：**
- 核心主题：{request.theme}
- 故事类型：{request.genre.value if request.genre else "自动判断"} - {genre_info.get("description", "")}
- 写作风格：{request.style.value}
- 目标字数：{request.word_count:,}字
- 章节规划：{request.chapter_count}章
- 目标读者：{request.target_audience}

**类型特色要求：**
{json.dumps(genre_info.get("style_prompts", {}), ensure_ascii=False, indent=2)}

**风格特点：**
{json.dumps(style_info.get("characteristics", []), ensure_ascii=False)}

请生成严格的JSON格式大纲，必须包含以下完整结构：

```json
{{
    "title": "具有吸引力和深度的标题",
    "subtitle": "副标题（可选，用于补充说明）",
    "author_note": "作者的话（100字内，{request.style.value}，吸引读者）",
    "one_line_pitch": "一句话概括故事核心（电梯推销版）",
    "genre": "精确的细分类型",
    "theme": "深层核心主题",
    "tone": "整体叙事基调（如：温暖励志、紧张悬疑、幽默轻松等）",

    "characters": {{
        "protagonist": {{
            "name": "主角姓名",
            "age": 年龄,
            "occupation": "职业",
            "personality": "核心性格特点（3-4个关键词）",
            "motivation": "主要动机和目标",
            "arc": "角色成长弧线描述",
            "background": "重要背景信息",
            "strengths": ["优点1", "优点2"],
            "weaknesses": ["缺点1", "缺点2"],
            "distinctive_traits": "独特特征或习惯"
        }},
        "supporting": [
            {{
                "name": "重要配角姓名",
                "role": "在故事中的作用",
                "relationship": "与主角的关系",
                "personality": "性格特点",
                "importance": 5,
                "conflict_source": "可能产生的冲突点"
            }},
            {{
                "name": "次要配角姓名", 
                "role": "功能性角色",
                "relationship": "关系定位",
                "personality": "简要性格",
                "importance": 3
            }}
        ]
    }},

    "world_setting": {{
        "time": "具体时间背景",
        "location": "主要地点和环境",
        "atmosphere": "环境氛围描述",
        "special_rules": "特殊设定或规则（如有）",
        "social_context": "社会背景和环境",
        "cultural_elements": "文化元素"
    }},

    "plot_structure": {{
        "hook": "开篇钩子（抓住读者的关键情节）",
        "inciting_incident": "激励事件（推动故事的关键事件）",
        "rising_action": [
            "第一次转折点",
            "矛盾升级点", 
            "危机加深点"
        ],
        "climax": "故事高潮（最紧张的冲突点）",
        "falling_action": "高潮后的发展",
        "resolution": "结局和主题升华"
    }},

    "chapter_outlines": [
        {{
            "chapter_num": 1,
            "title": "第1章：引人入胜的标题",
            "summary": "本章核心内容概要（50字内）",
            "key_events": ["关键事件1", "关键事件2", "转折点"],
            "characters_involved": ["主角", "配角A"],
            "mood": "本章情绪基调",
            "target_word_count": {request.word_count // request.chapter_count},
            "chapter_goal": "本章要达成的故事目标",
            "hook_ending": "章末悬念或钩子"
        }}
        // ... 共{request.chapter_count}章，每章都要有明确的目标和进展
    ],

    "themes_to_explore": [
        "主题1：具体阐述",
        "主题2：深度挖掘", 
        "主题3：情感共鸣"
    ],
    "key_symbols": [
        "象征物1：含义",
        "象征物2：作用"
    ],
    "target_readers": "{request.target_audience}",

    "writing_guidelines": {{
        "dialogue_ratio": "30-40%（对话推进情节）",
        "pacing": "张弛有度，高潮迭起",
        "language_style": "{request.style.value}特色",
        "sensory_details": "丰富的感官描写",
        "emotional_beats": "情感节奏控制"
    }}
}}
```

**创作原则：**
1. 故事必须有强烈的内在冲突和外在冲突
2. 人物要立体可信，有明显的成长弧线
3. 情节要紧凑有张力，每章都有明确目标
4. 适合{request.target_audience}的阅读习惯和兴趣点
5. 开篇必须在前三段内抓住读者注意力
6. 结构完整，主题深刻，具有现实意义

**特别注意：**
- 必须严格按照JSON格式输出，不要有任何格式错误
- 每章大纲都要详细具体，为后续创作提供清晰指导
- 人物设定要有足够深度，支撑整个故事发展
- 主题要有现实关怀，引发读者思考

请开始创作大纲：
"""
        return prompt

    def get_chapter_outline_prompt(self, outline: NovelOutline, chapter_num: int) -> str:
        """获取章节大纲细化提示词"""
        if chapter_num > len(outline.chapter_outlines):
            raise ValueError(f"章节编号超出范围: {chapter_num}")

        base_outline = outline.chapter_outlines[chapter_num - 1]

        # 获取前后章节信息用于连贯性
        prev_chapter = outline.chapter_outlines[chapter_num - 2] if chapter_num > 1 else None
        next_chapter = outline.chapter_outlines[chapter_num] if chapter_num < len(outline.chapter_outlines) else None

        prompt = f"""
基于总体故事大纲，请为第{chapter_num}章生成详细的创作大纲。

**故事背景：**
- 标题：{outline.title}
- 主题：{outline.theme}
- 基调：{outline.tone}
- 总章数：{len(outline.chapter_outlines)}

**本章基础信息：**
- 章节：第{chapter_num}章 - {base_outline.title}
- 概要：{base_outline.summary}
- 关键事件：{', '.join(base_outline.key_events)}
- 涉及角色：{', '.join(base_outline.characters_involved)}
- 目标字数：{base_outline.target_word_count}字

**角色信息：**
{json.dumps(outline.characters, ensure_ascii=False, indent=2)}

**前后章节衔接：**
{"- 上章情况：" + prev_chapter.summary if prev_chapter else "- 这是开篇章节"}
{"- 下章预告：" + next_chapter.summary if next_chapter else "- 这是结尾章节"}

请生成JSON格式的详细章节大纲：

```json
{{
    "chapter_num": {chapter_num},
    "title": "{base_outline.title}",
    "writing_goal": "本章的核心创作目标",

    "opening_scene": {{
        "location": "开场地点",
        "time": "具体时间（时段、天气等）",
        "mood": "开场氛围",
        "hook": "开篇抓人的方式",
        "transition": "与上章的过渡方式"
    }},

    "scene_breakdown": [
        {{
            "scene_num": 1,
            "location": "场景地点",
            "characters": ["角色1", "角色2"],
            "purpose": "场景目的和功能",
            "key_dialogue": ["重要对话要点1", "重要对话要点2"],
            "action_points": ["动作要点1", "动作要点2"],
            "emotional_beat": "情感节拍",
            "conflict": "本场景的冲突点",
            "revelation": "揭示的信息",
            "word_count_estimate": 800
        }},
        {{
            "scene_num": 2,
            "location": "场景地点",
            "characters": ["角色"],
            "purpose": "承接/转折作用",
            "key_dialogue": ["对话要点"],
            "action_points": ["行动"],
            "emotional_beat": "情感变化",
            "word_count_estimate": 700
        }},
        {{
            "scene_num": 3,
            "location": "高潮场景",
            "characters": ["主要角色"],
            "purpose": "章节高潮",
            "key_dialogue": ["关键对话"],
            "action_points": ["重要行动"],
            "emotional_beat": "情感高点",
            "conflict": "冲突爆发",
            "word_count_estimate": 700
        }}
    ],

    "conflict_structure": {{
        "internal_conflict": "角色内心冲突",
        "external_conflict": "外部阻碍或对抗",
        "stakes": "利害关系和后果",
        "tension_build": "张力营造方式"
    }},

    "character_development": {{
        "protagonist_arc": "主角在本章的成长变化",
        "relationship_changes": "人物关系的发展",
        "new_traits_revealed": "揭示的新特质"
    }},

    "ending_strategy": {{
        "resolution": "本章冲突如何解决",
        "cliffhanger": "悬念设置",
        "transition_to_next": "向下章的过渡",
        "emotional_impact": "希望达到的情感效果"
    }},

    "writing_notes": {{
        "pacing": "节奏控制建议",
        "dialogue_focus": "对话重点",
        "description_emphasis": "描写重点",
        "sensory_details": "感官细节要求",
        "style_notes": "风格注意事项"
    }},

    "quality_targets": {{
        "readability": "可读性目标",
        "emotional_engagement": "情感投入度",
        "plot_advancement": "剧情推进效果",
        "character_consistency": "人物一致性"
    }}
}}
```

**细化要求：**
1. 场景安排要有节奏感，不要平铺直叙
2. 对话要符合人物性格，推进情节
3. 每个场景都要有明确的目的和冲突
4. 情感节奏要有起伏，避免单调
5. 与整体故事弧线保持一致
6. 为下一章做好铺垫

请生成详细的章节创作大纲：
"""
        return prompt

    def get_chapter_content_prompt(self, chapter_outline: Dict, context: Dict) -> str:
        """获取章节内容创作提示词"""
        outline = context["outline"]
        previous_chapters = context.get("previous_chapters", [])
        chapter_num = chapter_outline.get("chapter_num", 1)

        # 生成前情摘要
        previous_summary = self._generate_previous_summary(previous_chapters)

        prompt = f"""
请根据详细大纲创作第{chapter_num}章的完整内容。

**故事背景：**
- 作品：{outline.title}
- 主题：{outline.theme}
- 基调：{outline.tone}
- 类型：{outline.genre}

**章节任务：**
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

**人物档案：**
{json.dumps(outline.characters, ensure_ascii=False, indent=2)}

**世界设定：**
{json.dumps(outline.world_setting, ensure_ascii=False, indent=2)}

**前情回顾：**
{previous_summary}

**创作要求：**

1. **字数控制**：
   - 严格控制在{chapter_outline.get('target_word_count', 2500) - 200}到{chapter_outline.get('target_word_count', 2500) + 200}字之间
   - 合理分配各场景篇幅

2. **结构安排**：
   - 开篇要有吸引力，迅速进入状态
   - 按照场景大纲推进，保持节奏
   - 结尾要有悬念或情感冲击

3. **对话创作**：
   - 对话比例占30-40%，推进剧情
   - 符合人物性格和身份
   - 自然流畅，有信息量
   - 适当运用潜台词

4. **描写技巧**：
   - 丰富的感官细节（视觉、听觉、触觉、嗅觉）
   - 环境描写烘托氛围
   - 人物神态和动作描写
   - 心理活动自然融入

5. **人物塑造**：
   - 保持性格一致性
   - 展现角色弧线变化
   - 通过行动展现性格
   - 关系发展要自然

6. **情节推进**：
   - 每个场景都要有目的
   - 冲突要有层次
   - 悬念和揭示平衡
   - 为后续章节埋下伏笔

7. **风格要求**：
   - 现代、流畅、有画面感
   - 避免过度文艺和晦涩
   - 适合{outline.target_readers}阅读
   - 体现{outline.tone}的基调

8. **特殊要求**：
   - 融入适当的知识点或思考（知乎风格特色）
   - 节奏张弛有度，有紧张有舒缓
   - {"章末要留悬念" if chapter_num < len(outline.chapter_outlines) else "结局要有升华"}

**创作指导：**
- 不要简单复述大纲，要有创造性发挥
- 对话要推进情节，不要无意义闲聊
- 每段都要有存在价值，删除冗余
- 情感要真实，避免做作
- 细节要服务于主题和氛围

**输出要求：**
- 直接输出章节内容，不要添加任何解释、标记或元信息
- 内容要完整流畅，可以直接发布
- 段落安排合理，便于阅读
- 语言生动有趣，引人入胜

请开始创作第{chapter_num}章：
"""
        return prompt

    def get_polish_prompt(self, chapter: Chapter, outline: NovelOutline) -> str:
        """获取内容润色提示词"""
        prompt = f"""
请对以下章节内容进行专业润色和优化。

**章节信息：**
- 章节：{chapter.title}
- 当前字数：{chapter.word_count}
- 在整体故事中的位置：第{chapter.chapter_num}章，共{len(outline.chapter_outlines)}章

**故事背景：**
- 作品：{outline.title}
- 主题：{outline.theme}
- 基调：{outline.tone}
- 类型：{outline.genre}

**原始内容：**
{chapter.content}

**润色目标：**

1. **语言优化**：
   - 删除冗余表达和重复词汇
   - 优化句式结构，提高流畅度
   - 增强画面感和代入感
   - 确保语言风格统一
   - 修正语法和标点错误

2. **结构改进**：
   - 优化段落结构和长度
   - 改善场景转换的连贯性
   - 调整信息披露的节奏
   - 强化开头和结尾的冲击力

3. **逻辑检查**：
   - 确保情节逻辑通顺合理
   - 检查时间线的一致性
   - 保持人物性格的连贯性
   - 验证与前文的衔接自然

4. **对话优化**：
   - 使对话更自然生动
   - 确保符合人物性格和身份
   - 通过对话推进情节发展
   - 添加适当的对话标签和动作

5. **描写增强**：
   - 丰富感官细节描写
   - 强化氛围营造
   - 优化环境和人物描写
   - 增加情感色彩

6. **节奏调整**：
   - 平衡叙述和对话的比例
   - 调整紧张和舒缓的节奏
   - 优化悬念和释放的时机
   - 确保整体节奏感

7. **主题深化**：
   - 强化主题表达
   - 增加情感深度
   - 提升思想内涵
   - 增强现实意义

8. **可读性提升**：
   - 确保符合目标读者习惯
   - 控制句子和段落长度
   - 增加趣味性和吸引力
   - 保持现代感和时代感

**润色原则：**
- 保持原有情节结构不变
- 不改变人物性格和关系
- 保留作者风格特色
- 字数变动控制在±10%以内
- 提升而不改变核心内容

**质量标准：**
- 语言流畅自然，无语法错误
- 情节推进合理，逻辑严密
- 人物形象生动，性格鲜明
- 氛围营造到位，感染力强
- 节奏把控恰当，引人入胜

请直接输出润色后的完整章节内容，不要添加任何解释、说明或格式标记：
"""
        return prompt

    def get_review_prompt(self, chapter: Chapter, chapter_outline: ChapterOutline,
                          outline: NovelOutline) -> str:
        """获取内容评审提示词"""
        prompt = f"""
请对以下章节内容进行专业的质量评审。

**评审标准：**

**章节目标：**
- 标题：{chapter_outline.title}
- 概要：{chapter_outline.summary}
- 关键事件：{', '.join(chapter_outline.key_events)}
- 目标字数：{chapter_outline.target_word_count}
- 预期氛围：{chapter_outline.mood}

**故事背景：**
- 作品：{outline.title}
- 主题：{outline.theme}
- 基调：{outline.tone}

**待评审内容：**
- 标题：{chapter.title}
- 实际字数：{chapter.word_count}
- 内容：{chapter.content[:500]}...（内容较长，已截取开头部分）

**评审维度：**

请从以下维度进行详细评分（1-5分，5分最佳）：

1. **内容完整性**：是否完整实现了章节目标和要求
2. **情节推进**：是否有效推进了整体故事发展
3. **人物刻画**：人物是否生动可信，性格是否一致
4. **语言质量**：文字表达是否流畅优美，风格是否统一
5. **节奏把控**：情节节奏是否适宜，张弛是否有度
6. **细节描写**：场景和氛围描写是否生动，感官细节是否丰富
7. **逻辑一致性**：是否与前文保持一致，逻辑是否通顺
8. **可读性**：是否符合目标读者口味，是否引人入胜
9. **对话质量**：对话是否自然，是否推进情节
10. **主题表达**：是否体现了故事主题，是否有深度

**评审报告格式：**

请返回以下JSON格式的评审报告：

```json
{{
    "overall_score": 总体评分(1-5),
    "detailed_scores": {{
        "completeness": 完整性评分,
        "plot_progression": 情节推进评分,
        "character_development": 人物刻画评分,
        "language_quality": 语言质量评分,
        "pacing": 节奏把控评分,
        "details_description": 细节描写评分,
        "logical_consistency": 逻辑一致性评分,
        "readability": 可读性评分,
        "dialogue_quality": 对话质量评分,
        "theme_expression": 主题表达评分
    }},
    "strengths": [
        "突出优点1",
        "突出优点2", 
        "突出优点3"
    ],
    "weaknesses": [
        "需要改进的问题1",
        "需要改进的问题2"
    ],
    "specific_suggestions": [
        "具体改进建议1：详细说明",
        "具体改进建议2：详细说明",
        "具体改进建议3：详细说明"
    ],
    "word_count_assessment": "字数评价和建议",
    "dialogue_ratio_check": "对话比例检查",
    "atmosphere_evaluation": "氛围营造评价",
    "character_consistency_check": "人物一致性检查",
    "plot_coherence_analysis": "情节连贯性分析",
    "recommendation": "accept/minor_revision/major_revision",
    "revision_priority": [
        "最重要的修改点1",
        "次重要的修改点2"
    ],
    "quality_improvement_tips": [
        "质量提升建议1",
        "质量提升建议2"
    ]
}}
```

**评审要求：**
- 客观公正，既要指出优点也要发现问题
- 具体详细，提供可操作的改进建议
- 专业严谨，基于文学创作标准
- 建设性强，帮助提升作品质量
- 考虑目标读者的接受度和喜好

请开始专业评审：
"""
        return prompt

    def _generate_previous_summary(self, previous_chapters: List[Chapter]) -> str:
        """生成前情提要"""
        if not previous_chapters:
            return "这是故事的开端，没有前情。"

        if len(previous_chapters) == 1:
            return f"前情概要：\n{previous_chapters[0].title}：{previous_chapters[0].content[:150]}..."

        # 最近几章的摘要
        recent_chapters = previous_chapters[-2:] if len(previous_chapters) > 2 else previous_chapters

        summary_parts = []
        for chapter in recent_chapters:
            # 提取关键信息
            content_preview = chapter.content[:200] + "..." if len(chapter.content) > 200 else chapter.content
            summary_parts.append(f"{chapter.title}：{content_preview}")

        return "前情概要：\n" + "\n\n".join(summary_parts)

    def get_agent_collaboration_prompt(self, agent_role: str, context: Dict) -> str:
        """获取Agent协作提示词"""
        agent_info = self.agent_config.get(agent_role, {})

        base_prompt = f"""
你是{agent_info.get('name', agent_role)}，{agent_info.get('description', '')}

**你的职责：**
{chr(10).join(['- ' + resp for resp in agent_info.get('responsibilities', [])])}

**工作风格：**
{agent_info.get('prompt_style', '')}

**协作要求：**
- 与其他AI团队成员协作
- 专注于你的专业领域
- 提供建设性的反馈和建议
- 保持高质量标准
- 为整体创作目标服务

**当前任务：**
{context.get('task_description', '根据上下文进行相应工作')}
"""
        return base_prompt

    def get_quality_evaluation_prompt(self, content: str, criteria: Dict) -> str:
        """获取质量评估提示词"""
        prompt = f"""
请对以下内容进行质量评估：

**评估内容：**
{content[:1000]}...

**评估标准：**
{json.dumps(criteria, ensure_ascii=False, indent=2)}

**评估要求：**
1. 客观公正地评估各项指标
2. 给出1-5分的具体评分
3. 提供详细的评分依据
4. 指出具体的优点和不足
5. 给出改进建议

**返回格式：**
```json
{{
    "overall_score": 综合评分,
    "dimension_scores": {{
        "criteria1": 分数,
        "criteria2": 分数
    }},
    "analysis": "详细分析",
    "suggestions": ["建议1", "建议2"]
}}
```

请开始评估：
"""
        return prompt