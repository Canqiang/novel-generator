class PromptTemplates:
    """提示词模板管理"""

    def get_outline_prompt(self, request) -> str:
        return f"""
请为以下主题创作一个中篇小说大纲：

主题：{request.theme}
类型：{request.genre if request.genre else "自动判断"}
目标字数：{request.word_count}字
章节数：{request.chapter_count}章

要求生成JSON格式的大纲，包含：
{{
    "title": "吸引人的标题",
    "subtitle": "副标题（可选）",
    "author_note": "作者的话（100字内，知乎风格）",
    "one_line_pitch": "一句话介绍",
    "genre": "具体类型",
    "theme": "核心主题",
    "tone": "整体基调（如：悬疑、温暖、黑色幽默等）",
    "characters": {{
        "protagonist": {{
            "name": "姓名",
            "age": 年龄,
            "occupation": "职业",
            "personality": "性格特点",
            "motivation": "核心动机",
            "arc": "角色成长弧线"
        }},
        "supporting": [
            {{
                "name": "姓名",
                "role": "角色定位",
                "relationship": "与主角关系",
                "personality": "性格特点"
            }}
        ]
    }},
    "world_setting": {{
        "time": "时间背景",
        "location": "地点",
        "atmosphere": "氛围描述",
        "special_rules": "特殊设定（如有）"
    }},
    "plot_structure": {{
        "hook": "开篇钩子",
        "inciting_incident": "激励事件",
        "rising_action": ["发展1", "发展2", "发展3"],
        "climax": "高潮",
        "falling_action": "高潮后发展",
        "resolution": "结局"
    }},
    "plot_points": [
        "第1章核心事件",
        "第2章核心事件",
        ...（{request.chapter_count}个）
    ],
    "themes_to_explore": ["主题1", "主题2", "主题3"],
    "key_symbols": ["象征物1", "象征物2"],
    "target_readers": "目标读者画像"
}}

注意：
1. 故事要有强烈的冲突和转折
2. 人物要立体有趣
3. 适合知乎读者口味（知识性、思辨性、现实关怀）
4. 开篇就要抓人
"""

    def get_chapter_outline_prompt(self, outline: Dict, chapter_num: int) -> str:
        return f"""
基于总体大纲，生成第{chapter_num}章的详细大纲。

总体故事：{outline["one_line_pitch"]}
本章对应的核心事件：{outline["plot_points"][chapter_num - 1]}

请生成JSON格式的章节大纲：
{{
    "title": "第{chapter_num}章标题",
    "opening_scene": {{
        "location": "场景地点",
        "time": "时间",
        "mood": "氛围",
        "hook": "开场钩子"
    }},
    "scenes": [
        {{
            "description": "场景描述",
            "purpose": "场景目的",
            "characters_present": ["角色1", "角色2"],
            "key_dialogue_points": ["对话要点1", "对话要点2"],
            "emotional_beat": "情绪节奏"
        }}
    ],
    "conflict": {{
        "type": "冲突类型",
        "description": "冲突描述",
        "stakes": "利害关系"
    }},
    "revelation": "本章揭示的信息（如有）",
    "cliffhanger": "章末悬念",
    "word_count_target": 2500,
    "pacing": "fast/medium/slow"
}}
"""

    def get_chapter_content_prompt(self, chapter_outline: Dict, context: Dict) -> str:
        return f"""
请根据大纲创作第{chapter_outline.get("chapter_num", "")}章内容。

章节大纲：
{json.dumps(chapter_outline, ensure_ascii=False, indent=2)}

人物设定：
{json.dumps(context["characters"], ensure_ascii=False, indent=2)}

前情提要：
{context.get("previous_summary", "这是第一章")}

写作要求：
1. 字数控制在2300-2700字
2. 多用对话推进剧情（对话比例30-40%）
3. 感官细节丰富（视觉、听觉、触觉等）
4. 节奏张弛有度
5. 保持人物性格一致性
6. 章末留悬念

风格要求：
- 文风：现代、流畅、有画面感
- 避免：过度文艺、晦涩难懂
- 知乎特色：偶尔加入有趣的知识点或思考

开始创作：
"""

    def get_polish_prompt(self, content: str, outline: Dict) -> str:
        return f"""
请润色以下章节内容，提升其文学质量。

原文：
{content[:1000]}...（原文过长，只显示开头）

润色要求：
1. 语言优化：
   - 删除冗余表达
   - 优化句式结构
   - 增强画面感

2. 情节检查：
   - 确保逻辑通顺
   - 检查时间线
   - 保持人设一致

3. 对话优化：
   - 使对话更自然
   - 符合人物性格
   - 推进剧情

4. 细节增强：
   - 添加感官细节
   - 强化氛围营造
   - 优化转场

5. 知乎风格：
   - 适当加入思考性内容
   - 保持可读性
   - 不要过度修饰

请直接输出润色后的完整内容，不要解释。
"""