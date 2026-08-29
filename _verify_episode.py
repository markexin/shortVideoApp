import sys, json
sys.path.insert(0, '.')

from projects.schema import Project, Shot
from pipeline.drama_storyboard import parse_storyboard_response, merge_storyboard_shots

raw = json.loads(open('projects_data/废柴药师逆伐仙门-270f8a43/project.json', encoding='utf-8').read())
p = Project.from_dict(raw)
print('向后兼容: 镜头数', len(p.shots), '全部 episode=1?', all(s.episode == 1 for s in p.shots))
print('script_units 集号示例:', [u['episode'] for u in p.script_units[:3]])

txt = json.dumps({"shots": [{"shot_id": 1, "scene_description": "x", "episode": 5, "duration": 4}]})
print('parse 单集打标 episode=', parse_storyboard_response(txt, episode=5)[0].episode, '(应为5)')
print('parse 无 episode 默认=', parse_storyboard_response(json.dumps({"shots": [{"shot_id": 1, "duration": 4}]}))[0].episode, '(应为1)')

existing = [Shot(shot_id=i, episode=(i - 1) // 6 + 1, duration=4.0) for i in range(1, 24)]
new = [Shot(shot_id=j, episode=5, duration=4.0) for j in range(1, 7)]
merged = merge_storyboard_shots(existing, new, episodes=[5])
print('merge 总数', len(merged), '(29) | shot_id连续', [m.shot_id for m in merged] == list(range(1, 30)))
print('merge ep5 段', [(m.shot_id, m.episode) for m in merged if m.episode == 5])
print('merge 前23仍 ep<=4:', all(m.episode <= 4 for m in merged if m.shot_id <= 23))

new2 = [Shot(shot_id=1, episode=5, duration=5.0), Shot(shot_id=2, episode=5, duration=5.0)]
merged2 = merge_storyboard_shots(merged, new2, episodes=[5])
print('重续写 ep5 不翻倍 总数', len(merged2), '(25) | ep5数', sum(1 for m in merged2 if m.episode == 5), '(2)')

from agent.commands import parse_command
print('命令 续写分镜 31 ->', parse_command('续写分镜 31').name, parse_command('续写分镜 31').args)
print('命令 续写分镜 31-40 ->', parse_command('续写分镜 31-40').name, parse_command('续写分镜 31-40').args)
print('ALL CORE CHECKS DONE')
