import re

import numpy as np
from langchain.tools import tool

from dreamcraft.app.protocols import ILLMClient, IWikiRepo, ISkillRepo


class KnowledgeService:
    def __init__(self, settings, wiki: IWikiRepo = None, llm: ILLMClient = None, skill: ISkillRepo = None):
        self.wiki = wiki
        self.llm = llm
        self.skill = skill
        self.skill_js_dir = settings.skill_js_dir

    def query_wiki(self, keyword, items=3) -> list[dict]:
        query_embedding = self.llm.embed(keyword)
        results = self.wiki.query(query_embedding, top_k=items*2+1000)
        
        final = []
        for r in results:
            if len(r['document'].content) < 10:  # 过滤掉过短的内容
                continue
            final.append(r)
            if len(final) >= items:
                break
        
        return final
    
    def query_skill(self, keyword, items=3) -> list[dict]:
        query_embedding = self.llm.embed(keyword)
        return self.skill.query(query_embedding, top_k=items)
    
    def add_skill(self, skill):
        skill_embedding = self.llm.embed(skill.summary).reshape(1, -1).astype('float32')
        self.skill.add(skill, skill_embedding)
    
    def get_skill(self, ref):
        return self.skill.get(ref)
    
    def grep_wiki_files(self, pattern: str, max_results: int = 5) -> list[dict]:
        return self.wiki.grep_files(pattern, max_results)
    
    def read_wiki_section(self, file_name: str, section_title: str) -> str:
        return self.wiki.read_section(file_name, section_title)
    
    def load_js_skills(self):
        all_s = self.skill.load_js_dir_skills(self.skill_js_dir)
        self.skill.update_private_skills(all_s.private_skills)
        for _skill in all_s.skills:
            if _skill not in self.skill.skills:
                self.add_skill(_skill)
            else:
                self.skill.skills_dict[_skill.name] = _skill
                print(f"更新技能 {_skill.name} 的信息，但不更新向量和索引")
        self.skill.update_all_dependencies()

        
    def inject_dependencies(self, code: str):
        dep = set()
        for skill in self.skill.skills:
            if skill.name.split('(')[0].split('function')[-1] in code:
                dep.add(skill)
                dep.update(self.skill.resolve_dependencies(skill))
        for s in dep:
            if s.function:
                code += f"\n\n{s.function}"
        code =re.sub(r'\n+', '\n', code)
        return code
