import pathlib
import re


def grep_files(pattern: str, path: pathlib.Path, include: str = "*", max_results: int = -1, with_heading_hierarchy: bool = True) -> list[dict]:
    try:
        regex = re.compile(pattern, re.I | re.M)
    except re.error as e:
        return f"⚠️ 正则表达式语法错误: {str(e)}"

    match = []
    for p in path.rglob(include):
        if with_heading_hierarchy and p.suffix != ".md":
            with_heading_hierarchy = False
        with open(p, 'r', encoding='utf-8') as f:
            # 检测能否读取文件内容，避免编码错误导致的崩溃
            try:
                lines = f.readlines()
            except UnicodeDecodeError:
                print(f"⚠️ 无法读取文件内容: {p}")
                continue
            for i, line in enumerate(lines):
                if regex.search(line):
                    hignlighted_line = regex.sub(lambda m: f"=={m.group(0)}==", line.strip())
                    highlighted_preview = regex.sub(lambda m: f"=={m.group(0)}==", "".join(lines[max(0, i-1):min(i+2, len(lines))]).strip())
                    heading_hierarchy = get_md_heading_hierarchy(p, i + 1) if with_heading_hierarchy else []
                    # if heading_hierarchy[0] == f'# {p.name.split(".")[0].replace("_", " ")}':  # 如果第一级标题就是文件名，去掉这一层
                    #     heading_hierarchy.pop(0)
                    match.append({
                        "file": p.name,
                        "line": i + 1,
                        "match_line": hignlighted_line,
                        "heading_hierarchy": heading_hierarchy,
                        "preview": highlighted_preview
                    })
            
    group = {}
    for m in match:
        group.setdefault(m["file"], []).append(m)
    results = []
    if max_results > 0:
        k = max_results/len(match) if match else 0.0
        remaining: float = float(max_results)-(1e-3)
        remaining_actual = max_results
        for f, previews in group.items():
            output_count_float : float = len(previews)*k
            output_count_int = int(output_count_float)
            remaining -= output_count_float
            remaining_actual -= output_count_int
            output_count = output_count_int
            while remaining_actual -1 > remaining and len(previews) > output_count:
                output_count += 1
                remaining_actual -= 1
            if output_count > 0:
                if with_heading_hierarchy:
                    _preview = [{
                        'ln': p['line'], 
                        'content': f"{p['match_line']}",
                        'heading_hierarchy': p['heading_hierarchy']
                    } for p in previews[:output_count]]
                else:
                    _preview = [{
                        'ln': p['line'], 
                        'content': f"{p['match_line']}"
                    } for p in previews[:output_count]]
                results.append({
                    "file": f,
                    "matches": len(previews),
                    "preview": _preview
                })
    else:
        for f, previews in group.items():
            if with_heading_hierarchy:
                _preview = [{
                    'ln': p['line'], 
                    'content': f"{p['match_line']}",
                    'heading_hierarchy': p['heading_hierarchy']
                } for p in previews]
            else:
                _preview = [{
                    'ln': p['line'], 
                    'content': f"{p['match_line']}"
                } for p in previews]
            results.append({
                "file": f,
                "matches": len(previews),
                "preview": _preview
            })

    return {
        "pattern": pattern,
        "match_files": len(group),
        "match_lines": len(match),
        "is_truncated": max_results > 0 and len(match) > max_results,
        "snippets": results
    }

def get_md_heading_hierarchy(file_path: str, line_number: int) -> list[str]:
    """
    根据行号，向上回溯所有层级的父标题。
    返回示例: ['# Blocks', '## Decorative Blocks', '### Head']
    """
    hierarchy = []
    current_min_level = float('inf') # 初始设为无限大
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # 只读取到目标行之前的行
        lines = f.readlines()[:line_number]
        
    # 从目标行开始向上反向遍历
    for line in reversed(lines):
        # 匹配标题行，如 "## Drops"
        match = re.match(r"^(#+)\s+(.*)", line.strip())
        if match:
            level_str = match.group(1)
            level_num = len(level_str) # # 的个数
            title = match.group(2)
            
            # 如果当前标题的层级比已找到的层级更高(数字更小)
            if level_num < current_min_level:
                hierarchy.append(f"{level_str} {title}")
                current_min_level = level_num
                
            # 如果已经触达一级标题(#)，可以提前结束
            if current_min_level == 1:
                break
                
    # 翻转列表，使其符合从大到小的逻辑顺序
    return hierarchy[::-1]

def read_md_section(file_path: str, section_name: str):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    header_re = rf"^(?P<lv>#+)\s+{re.escape(section_name)}\b.*$"
    header_match = re.search(header_re, content, re.M)
    if not header_match:
        return "Section not found."

    level_str = header_match.group('lv')
    level_num = len(level_str)
    
    start_index = header_match.end()
    stop_pattern = rf"(\r?\n#{{1,{level_num}}}\s+|$)"

    remaining_content = content[start_index:]
    content_match = re.search(rf"(?P<text>.*?)(?={stop_pattern})", remaining_content, re.S)
    if content_match:
        return (level_str + " " + section_name + "\n" + content_match.group('text')).strip()
    
    return "Section not found."