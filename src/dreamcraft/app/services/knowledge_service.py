import numpy as np
from langchain.tools import tool

from dreamcraft.app.protocols import ILLMClient, IWikiRepo, ISkillRepo


class KnowledgeService:
    def __init__(self, wiki: IWikiRepo = None, llm: ILLMClient = None, skill: ISkillRepo = None):
        self.wiki = wiki
        self.llm = llm
        self.skill = skill

    def query_wiki(self, keyword, items=3):
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
    
    def query_skill(self, keyword, items=3):
        query_embedding = self.llm.embed(keyword)
        return self.skill.query(query_embedding, top_k=items)
    

    def add_skill(self, skill):
        skill_embedding = self.llm.embed(skill.summary).reshape(1, -1).astype('float32')
        self.skill.add(skill, skill_embedding)
    