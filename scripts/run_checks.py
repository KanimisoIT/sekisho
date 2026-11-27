#!/usr/bin/env python3
"""指摘の束を回す。.sekisho/checks/ の台本を一本ずつ走らせ、一本でも落ちたら赤。

台本の頭(最初の十行)には「由来: #<番号> <YYYY-MM-DD>」を書く。無ければ赤。
公開のリポジトリでは、頭に言葉の引用(「…」)を書かない(言葉は非公開の所に置く)。
"""
import os
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Report

DIR = pathlib.Path('.sekisho/checks')
ORIGIN = re.compile(r'由来:\s*#\d+\s+20\d\d-\d\d-\d\d')
RUNNERS = {'.py': [sys.executable, '-I'], '.sh': ['bash'], '.mjs': ['node'], '.js': ['node']}
TIMEOUT = 300


def main():
    r = Report('指摘の束')
    if not DIR.is_dir():
        print('指摘の束はまだ無い')
        return r.finish()
    public = os.environ.get('REPO_PUBLIC') == 'true'
    files = sorted(p for p in DIR.iterdir() if p.is_file() and p.suffix in RUNNERS)
    for p in files:
        head = '\n'.join(p.read_text(encoding='utf-8').splitlines()[:10])
        if not ORIGIN.search(head):
            r.fail('由来の欠け', str(p), '頭に「由来: #番号 日付」が無い')
        if public and '「' in head:
            r.fail('公開の場に言葉', str(p), '公開のリポジトリの台本の頭に引用を書かない')
        try:
            done = subprocess.run([*RUNNERS[p.suffix], str(p)], capture_output=True, text=True,
                                  encoding='utf-8', timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            r.fail('止まった疑い', str(p), f'{TIMEOUT} 秒で終わらない')
            continue
        if done.returncode != 0:
            tail = (done.stdout + done.stderr).strip().splitlines()[-3:]
            r.fail('指摘の再発', str(p), ' / '.join(tail)[:200])
    print(f'指摘の束: {len(files)} 本を回した')
    return r.finish()


if __name__ == '__main__':
    sys.exit(main())
