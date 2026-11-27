"""関所の台本が共通で使う小さな道具。標準の道具だけで動く(ランナーに何も入れない)。"""
import json
import pathlib
import subprocess

CONFIG = pathlib.Path('.sekisho/config.json')
ALLOW = pathlib.Path('.sekisho/allow.json')


def git(*args, check=True):
    r = subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8')
    if check and r.returncode != 0:
        raise SystemExit(f'git {" ".join(args)} が失敗: {r.stderr.strip()}')
    return r.stdout


def has_base(base):
    return bool(base) and set(base) != {'0'} and subprocess.run(
        ['git', 'cat-file', '-e', f'{base}^{{commit}}'], capture_output=True).returncode == 0


def changed_files(base, head):
    """取り込み先から変わったファイル。状態(A/M/D/R)と名前の組。"""
    out = []
    for line in git('diff', '--name-status', '-M', f'{base}...{head}').splitlines():
        parts = line.split('\t')
        out.append((parts[0][0], parts[1], parts[-1]))
    return out


def added_lines(base, head, path=None):
    """取り込み先から足された行。(ファイル名, 行) の組。"""
    args = ['diff', '-U0', '--no-color', f'{base}...{head}']
    if path:
        args += ['--', path]
    cur, out = None, []
    for line in git(*args).splitlines():
        if line.startswith('+++ '):
            cur = line[6:] if line.startswith('+++ b/') else None
        elif line.startswith('+') and not line.startswith('+++') and cur:
            out.append((cur, line[1:]))
    return out


def removed_lines(base, head, path):
    return [line[1:] for line in git('diff', '-U0', '--no-color', f'{base}...{head}', '--', path).splitlines()
            if line.startswith('-') and not line.startswith('---')]


def load_json(path, default):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


class Report:
    def __init__(self, name):
        self.name, self.red = name, []

    def fail(self, kind, where, msg):
        self.red.append(f'赤|{kind}|{where}|{msg}')

    def finish(self):
        for line in self.red:
            print(line)
        print(f'{self.name}: ' + (f'赤 {len(self.red)} 件' if self.red else '緑'))
        return 1 if self.red else 0
