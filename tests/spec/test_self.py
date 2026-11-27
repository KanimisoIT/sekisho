"""検査の検査。わざと誤りを入れた変更が全部赤になり、まっとうな変更が緑になることを確かめる。

一本でも緑に変わる本体の変更は取り込まない(この試験が落ちる)。見本は足すだけ。
"""
import json
import pathlib
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent.parent / 'scripts'


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def repo(tmp_path, base_files, head_files, head_deletes=()):
    d = tmp_path / 'repo'
    d.mkdir(parents=True)
    sh(d, 'git', 'init', '-q', '-b', 'main')
    sh(d, 'git', 'config', 'user.email', 't@example.invalid')
    sh(d, 'git', 'config', 'user.name', 't')
    for name, body in base_files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding='utf-8')
    sh(d, 'git', 'add', '-A')
    sh(d, 'git', 'commit', '-qm', 'base', '--allow-empty')
    base = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=d, capture_output=True, text=True).stdout.strip()
    for name, body in head_files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(body, encoding='utf-8')
    for name in head_deletes:
        (d / name).unlink()
    sh(d, 'git', 'add', '-A')
    sh(d, 'git', 'commit', '-qm', 'head', '--allow-empty')
    return d, base


def run(d, script, *args, env=None):
    r = subprocess.run([sys.executable, '-I', str(SCRIPTS / script), *args], cwd=d, capture_output=True,
                       text=True, encoding='utf-8', env=env)
    return r.returncode, r.stdout + r.stderr


SPEC = 'def test_flush_is_150():\n    assert FLUSH == 150\n'
CHECK = '# 由来: #3 2026-11-26\nimport sys\nsys.exit(0)\n'
APP = 'export const BUILD = 10;\n'

BAD_GUARD = [
    ('黙らせる書き込み', {}, {'app.js': 'x(); // eslint-disable-line\n'}, ()),
    ('黙らせる書き込み', {}, {'game.py': 'import os  # noqa\n'}, ()),
    ('黙らせる書き込み', {}, {'tests/a.test.js': 'it.skip("r4", () => {})\n'}, ()),
    ('黙らせる書き込み', {}, {'tests/test_a.py': '@pytest.mark.skip\ndef test_x():\n    pass\n'}, ()),
    ('足すだけの所を変えた', {'tests/spec/test_rules.py': SPEC},
     {'tests/spec/test_rules.py': SPEC.replace('150', '100')}, ()),
    ('足すだけの所を変えた', {'.sekisho/checks/003.py': CHECK}, {}, ('.sekisho/checks/003.py',)),
    ('試験の数が減った', {'tests/test_a.py': 'def test_a():\n    pass\n\ndef test_b():\n    pass\n'},
     {'tests/test_a.py': 'def test_a():\n    pass\n'}, ()),
    ('守りの設定を弱めた', {'tsconfig.json': '{\n  "compilerOptions": {\n    "strict": true\n  }\n}\n'},
     {'tsconfig.json': '{\n  "compilerOptions": {\n    "strict": false\n  }\n}\n'}, ()),
    ('守りの設定を弱めた', {'eslint.config.js': 'export default [{ rules: { "no-empty": "error" } }];\n'},
     {'eslint.config.js': 'export default [{ rules: { "no-empty": "off" } }];\n'}, ()),
    ('守りの設定を弱めた', {'package.json': '{\n  "scripts": {\n    "test": "vitest run"\n  }\n}\n'},
     {'package.json': '{\n  "scripts": {\n    "test": "echo ok"\n  }\n}\n'}, ()),
    ('守りの設定を消した', {'pyproject.toml': '[tool.ruff]\nline-length = 100\n'}, {}, ('pyproject.toml',)),
    ('守りの設定を弱めた', {'.sekisho/config.json': '{"version_sync": []}\n'},
     {'.sekisho/config.json': '{"version_sync": [], "guard_exempt": ["app.js"]}\n'}, ()),
]


@pytest.mark.parametrize('kind,base,head,deletes', BAD_GUARD, ids=[f'{k}-{i}' for i, (k, *_) in enumerate(BAD_GUARD)])
def test_guard_bad_is_red(kind, base, head, deletes, tmp_path):
    d, b = repo(tmp_path, base or {'README.md': 'x\n'}, head, deletes)
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27')
    assert code == 1 and kind in out, out


def test_guard_good_is_green(tmp_path):
    d, b = repo(tmp_path, {'tests/spec/test_rules.py': SPEC, '.sekisho/checks/003.py': CHECK, 'app.js': APP},
                {'tests/spec/test_more.py': 'def test_r4_hidden():\n    assert True\n',
                 '.sekisho/checks/004.py': '# 由来: #4 2026-11-27\nimport sys\nsys.exit(0)\n',
                 'app.js': APP + 'export const add = (a, b) => a + b;\n',
                 'tsconfig.json': '{\n  "compilerOptions": {\n    "strict": true\n  }\n}\n'})
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27')
    assert code == 0, out


def test_guard_retire_by_naming(tmp_path):
    d, b = repo(tmp_path, {'.sekisho/checks/003.py': CHECK},
                {'.sekisho/checks/009.py': '# 由来: #9 2026-11-27\n# 退く: .sekisho/checks/003.py\nimport sys\nsys.exit(0)\n'},
                ('.sekisho/checks/003.py',))
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27')
    assert code == 0, out


def test_guard_allow_rules(tmp_path):
    allow = [{'path': 'app.js', 'pattern': 'eslint-disable-line', 'reason': '外の部品の型の誤り', 'until': '2026-12-20'}]
    d, b = repo(tmp_path, {'.sekisho/allow.json': json.dumps(allow)}, {'app.js': 'x(); // eslint-disable-line\n'})
    assert run(d, 'guard.py', '--base', b, '--today', '2026-11-27')[0] == 0
    assert run(d, 'guard.py', '--base', b, '--today', '2026-12-21')[0] == 1
    long = [dict(allow[0], until='2027-03-01')]
    d2, b2 = repo(tmp_path / 'x', {}, {'.sekisho/allow.json': json.dumps(long)})
    code, out = run(d2, 'guard.py', '--base', b2, '--today', '2026-11-27')
    assert code == 1 and '許しの期限が長い' in out


def test_guard_exempt_only_for_sekisho_self(tmp_path):
    d, b = repo(tmp_path, {'.sekisho/config.json': '{"guard_exempt": ["scripts/*"]}\n'},
                {'scripts/guard.py': "PATTERN = 'eslint-disable'\n", 'app.js': '// eslint-disable\n'})
    selfenv = dict(__import__('os').environ, SEKISHO_SELF='true')
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27', env=selfenv)
    assert code == 1 and 'app.js' in out and 'scripts/guard.py' not in out, out
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27')
    assert code == 1 and 'scripts/guard.py' in out, out


def test_guard_exempt_added_in_same_change_is_ignored(tmp_path):
    selfenv = dict(__import__('os').environ, SEKISHO_SELF='true')
    d, b = repo(tmp_path, {'README.md': 'x\n'},
                {'.sekisho/config.json': '{"guard_exempt": ["app.js"]}\n', 'app.js': '// eslint-disable\n'})
    code, out = run(d, 'guard.py', '--base', b, '--today', '2026-11-27', env=selfenv)
    assert code == 1 and 'app.js' in out, out


@pytest.mark.parametrize('line', [
    '// 以前は 120 だったが 150 に修正した',
    '# 2026-11-26 R4 の三枚目を伏せるため追加',
    '// fixed flush value',
    '<!-- previously hidden -->',
])
def test_history_comment_is_red(line, tmp_path):
    name = 'index.html' if line.startswith('<!--') else ('rules.py' if line.startswith('#') else 'rules.js')
    d, b = repo(tmp_path, {'README.md': 'x\n'}, {name: line + '\n'})
    code, out = run(d, 'comments.py', '--base', b)
    assert code == 1, out


def test_present_comment_is_green(tmp_path):
    d, b = repo(tmp_path, {'README.md': 'x\n'}, {'rules.js': '// フラッシュは役の強さで三番目\nexport const FLUSH = 150;\n'})
    assert run(d, 'comments.py', '--base', b)[0] == 0


def test_version_sync(tmp_path):
    cfg = {'version_sync': [{'file': 'app.js', 'pattern': r'BUILD\s*=\s*(\d+)'},
                            {'file': 'version.json', 'pattern': r'"build"\s*:\s*(\d+)'}]}
    d, _ = repo(tmp_path, {'.sekisho/config.json': json.dumps(cfg), 'app.js': APP, 'version.json': '{"build": 10}'}, {})
    assert run(d, 'version_sync.py')[0] == 0
    (d / 'version.json').write_text('{"build": 9}', encoding='utf-8')
    code, out = run(d, 'version_sync.py')
    assert code == 1 and '食い違う' in out


def test_run_checks(tmp_path):
    d, _ = repo(tmp_path, {'.sekisho/checks/003.py': CHECK,
                           '.sekisho/checks/004.py': '# 由来: #4 2026-11-27\nimport sys\nsys.exit(1)\n',
                           '.sekisho/checks/005.py': 'import sys\nsys.exit(0)\n'}, {})
    code, out = run(d, 'run_checks.py')
    assert code == 1 and '指摘の再発' in out and '由来の欠け' in out
    pub = dict(__import__('os').environ, REPO_PUBLIC='true')
    d2, _ = repo(tmp_path / 'p', {'.sekisho/checks/006.py': '# 由来: #6 2026-11-27 「フラッシュは150」\n'}, {})
    code, out = run(d2, 'run_checks.py', env=pub)
    assert code == 1 and '公開の場に言葉' in out
