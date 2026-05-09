import json
import os
from pathlib import Path
import re
import faiss
import numpy as np
from dreamcraft.domain.skill import LoadJSResult, LoadJSResults, Skill

class SkillRepo:
    def __init__(self, settings):
        self.dim = settings.embedding_dimension
        self.json_path = settings.skill_documents_path
        self.npy_path = settings.skill_embeddings_path
        self.faiss_index_path = settings.skill_faiss_index_path
        
        self.private_skills:list[Skill] = []

        self.skills: list[Skill] = self.load_skills_from_json(self.json_path)
        try:
            self.embeddings: np.ndarray = np.load(self.npy_path) 
        except:
            self.embeddings: np.ndarray = None
        self.skills_dict = {skill.identifier: skill for skill in self.skills}
        self.faiss_index = self.load_faiss_index(self.faiss_index_path)
        
    def __getitem__(self, key: str | int) -> Skill:
        if isinstance(key, int):
            return self.skills[key]
        elif isinstance(key, str):
            return self.skills_dict[key]
        else:
            raise KeyError("Key must be either int (index) or str (skill name)")

    def load_js_skill(self, js_path: Path)-> LoadJSResult:
        with open(js_path, 'r', encoding='utf-8') as f:
            code_lines = f.readlines()
        
        is_comment = False
        description_lines = []
        name_line = ''
        code_begin = 0
        is_private = False
        for i, line in enumerate(code_lines):
            line = line.replace('"',"'")
            if line.strip().startswith('//'):
                if re.search(r'@\s*dreamcraft\s*-private', line.strip()):
                    is_private = True
                description_lines.append(line.strip()[2:])
            elif line.strip().startswith('/*'):
                is_comment = True
                description_lines.append(line.strip()[2:].lstrip(" *"))
            elif is_comment:
                if line.strip().endswith('*/'):
                    is_comment = False
                    description_lines.append(line.strip()[:-2].lstrip(" *"))
                else:
                    line = line.lstrip(" *")
                    description_lines.append(line.strip())
            else:
                body = "".join(code_lines[i:])
                left_paren_count = -1
                for i, c in enumerate(body):
                    if c == '(':
                        left_paren_count = 1 if left_paren_count == -1 else left_paren_count + 1
                    elif c == ')':
                        left_paren_count -= 1
                    if left_paren_count == 0:
                        name_end_index = i
                        break
                name = body[:name_end_index+1].strip()
                name = re.sub(r'\s*\n\s*', '', name)
                break
                    
            
        description = ''.join(description_lines).strip()
        function = body
        provider = js_path.parent.name
        return LoadJSResult(skill=Skill(name=name, description=description, function=function, provider=provider), is_private=is_private)


    def load_js_dir_skills(self, dir: Path) -> LoadJSResults:
        #获取目录下所有子目录, pathlib实现
        subdirs = [entry for entry in dir.iterdir() if entry.is_dir()]
        #遍历每个子目录，获取其中的js文件
        js_files = []
        for subdir in subdirs:
            for root, dirs, files in os.walk(subdir):
                for file in files:
                    if file.endswith('.js'):
                        js_files.append(Path(root) / file)
        
        skills = []
        private_skills = []
        for js_file in js_files:
            result = self.load_js_skill(js_file)
            skill = result.skill
            is_private = result.is_private
            if skill is not None:
                if is_private:
                    private_skills.append(skill)
                else:
                    skills.append(skill)
            
        return LoadJSResults(skills=skills, private_skills=private_skills)
    
    def update_dependencies(self, skill: Skill):
        if not skill.function:
            return
        skill.dependencies = set()
        for search_skill in list(dict.fromkeys(self.skills + self.private_skills)):
            if not search_skill.function or search_skill.name == skill.name:
                continue

            if search_skill.name.split('(')[0].split('function')[-1] in skill.function:
                skill.dependencies.add(search_skill.identifier)
    

    def resolve_dependencies(self, skill: Skill, layers: list[Skill] = None):
        dep = set()
        if not layers:
            layers = [skill]
        for identifier in skill.dependencies:
            _skill = self.skills_dict.get(identifier)
            if _skill is None:
                print(f"警告: 技能 {skill.name} 的依赖项 {identifier} 在技能库中未找到，可能是因为未正确加载或解析")
                continue
            dep.add(_skill)
            if _skill in layers:
                continue
            new_deps = self.resolve_dependencies(_skill, layers + [_skill])
            dep.update(new_deps)
        return dep

    def update_all_dependencies(self):
        for skill in self.skills + self.private_skills:
            self.update_dependencies(skill)

    def load_skills_from_json(self, json_path):
        if not json_path.exists():
            return []
        
        if os.path.getsize(json_path) == 0:
            print(f"警告: {json_path} 是空的，返回空列表")
            return []

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                skills = json.load(f)
            lst = [Skill(**doc) for doc in skills]
            for x in lst:
                if not x.provider:
                    x.provider = json_path.stem
            return list(dict.fromkeys(lst))  # 去重，保持顺序
        except json.JSONDecodeError:
            print(f"错误: {json_path} 格式非法")
            return []
    
    def add_private_skill(self, new_private_skill: Skill):
        if new_private_skill in self.private_skills:
            return
        self.private_skills.append(new_private_skill)
        self.update_dependencies(new_private_skill)

    def update_private_skills(self, new_private_skills: list[Skill]):
        for skill in new_private_skills:
            self.add_private_skill(skill)
        self.private_skills = list(dict.fromkeys(self.private_skills))

    def load_faiss_index(self, index_path):
        if not index_path.exists():
            faiss_index = faiss.IndexFlatL2(self.dim)
            for i in range(len(self.skills)):
                faiss_index.add(self.embeddings[i:i+1])
            return faiss_index
        faiss_index = faiss.read_index(str(index_path))
        return faiss_index
    
    def save_skills_to_json(self, json_path):
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([doc.dict for doc in self.skills], f, ensure_ascii=False, indent=4)

    def save_faiss_index(self, index_path):
        faiss.write_index(self.faiss_index, str(index_path))
    
    def query(self, query_embedding, top_k=3) -> list[dict]:
        actual_k = min(top_k, len(self.skills))
        distances, indices = self.faiss_index.search(query_embedding, actual_k)
        return [
            {
                "skill": self.skills[i],
                "l2_distance": distances[0][j]
            }
            for j, i in enumerate(indices[0])
            if i != -1  # FAISS 在搜索结果不足时会返回 -1，建议过滤掉
        ]

    def add(self, skill: Skill, skill_embedding: np.ndarray):
        """添加新技能到知识库，并更新 FAISS 索引和文档列表"""
        if skill in self.skills:
            print(f"技能 {skill.name} 已存在，跳过添加")
            return
        print(f"添加技能 {skill.name} 到知识库")
        self.skills.append(skill)
        self.skills_dict[skill.name] = skill
        if self.embeddings is not None:
            self.embeddings = np.vstack([self.embeddings, skill_embedding])
        self.faiss_index.add(skill_embedding)
        self.save_skills_to_json(self.json_path)
        self.save_faiss_index(self.faiss_index_path)
        self.update_dependencies(skill)
    
    def get(self, ref: int | str) -> Skill:
        """根据索引或技能名称获取技能信息"""
        if isinstance(ref, int):
            return list(self.skills)[ref]
        elif isinstance(ref, str):
            return self.skills_dict.get(ref)
        else:
            raise KeyError("Reference must be either int (index) or str (skill name)")