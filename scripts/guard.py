#!/usr/bin/env python3
"""抜け道の封じ。取り込み先(base)と比べて、検査を弱めて通す手を赤にする。

一 黙らせる書き込みの新顔(lint を止める注釈・型の無視・試験の飛ばし ほか)。許しの一覧にある物だけ通す。
二 許しの一覧の期限切れ・上限超え・期限の無い行。
三 指摘の束(.sekisho/checks/)と仕様の試験(tests/spec/)は足すだけ。変える・消すは赤。
   引退は、新しい台本の頭の「退く: <道筋>」が古い台本を名指ししたときだけ。
四 試験の数が取り込み先より減った。
五 守りの設定(lint・型・試験の設定、関所の設定)から行が消えた、または弱める語の行が足された。
"""
import argparse
import datetime
import fnmatch
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ALLOW, Report, added_lines, changed_files, git, has_base, load_json, removed_lines

SUPPRESS = re.compile(
    r'eslint-disable|@ts-ignore|@ts-nocheck|@ts-expect-error|#\s*noqa|#\s*type:\s*ignore|pylint:\s*disable|'
    r'pyright:\s*ignore|\b(?:it|test|describe)\.(?:skip|todo)\s*\(|\bx(?:it|describe|test)\s*\(|'
    r'pytest\.mark\.(?:skip|xfail)|unittest\.skip|\.only\s*\(')
APPEND_ONLY = ('.sekisho/checks/', 'tests/spec/')
RETIRE = re.compile(r'退く:\s*(\S+)')
TEST_DEF = re.compile(r'^\s*(?:def test_|async def test_|(?:it|test)\s*\()', re.M)
PROTECTED = re.compile(r'(^|/)(eslint\.config\.[cm]?[jt]s|\.eslintrc(\.\w+)?|tsconfig[\w.-]*\.json|pyproject\.toml|'
                       r'setup\.cfg|\.?ruff\.toml|pyrightconfig\.json|\.sekisho/config\.json)$')
WEAKEN = re.compile(r'"off"|\boff\b|"warn"|ignore|exclude|exempt|disable|skip|noqa|"strict"\s*:\s*false|'
                    r'"noImplicitAny"\s*:\s*false|allowJs|"checkJs"\s*:\s*false', re.I)
PKG_GUARDED = re.compile(r'"(test|lint|typecheck|check)"\s*:')
ALLOW_CAP = 10
ALLOW_DAYS = 30


def base_exempt(base):
    """検査を外す道筋。関所の本体の自己試験(SEKISHO_SELF=true)のときだけ効き、アプリでは使わない。
    判定の設定は取り込み先の版から読む(同じ変更の中で外せないように)。"""
    if os.environ.get('SEKISHO_SELF') != 'true':
        return []
    try:
        return json.loads(git('show', f'{base}:.sekisho/config.json', check=False) or '{}').get('guard_exempt', [])
    except json.JSONDecodeError:
        return []


def check_suppressions(base, head, allow, r):
    exempt = base_exempt(base)
    for path, line in added_lines(base, head):
        if path.startswith('.sekisho/') or any(fnmatch.fnmatch(path, g) for g in exempt) or not SUPPRESS.search(line):
            continue
        if not any(path == a.get('path') and a.get('pattern', '') in line for a in allow):
            r.fail('黙らせる書き込み', path, line.strip()[:80])


def check_allow(allow, today, r):
    if len(allow) > ALLOW_CAP:
        r.fail('許しの上限', str(ALLOW), f'{len(allow)} 行(上限 {ALLOW_CAP})')
    for a in allow:
        until = a.get('until')
        if not (a.get('path') and a.get('pattern') and a.get('reason') and until):
            r.fail('許しの欠け', str(ALLOW), f'path・pattern・reason・until のどれかが無い: {a}')
            continue
        d = datetime.date.fromisoformat(until)
        if d < today:
            r.fail('許しの期限切れ', a['path'], f'{until} に切れた')
        elif (d - today).days > ALLOW_DAYS:
            r.fail('許しの期限が長い', a['path'], f'{until}(今日から {ALLOW_DAYS} 日まで)')


def check_append_only(base, head, r):
    changes = changed_files(base, head)
    retired = set()
    for status, _old, new in changes:
        if status == 'A' and new.startswith(APPEND_ONLY):
            body = git('show', f'{head}:{new}')
            retired |= set(RETIRE.findall('\n'.join(body.splitlines()[:10])))
    for status, old, new in changes:
        for path in {old, new}:
            if path.startswith(APPEND_ONLY) and status in 'MDR' and path not in retired:
                r.fail('足すだけの所を変えた', path, f'状態 {status}。引退させるなら新しい台本の頭に「退く: {path}」')


def count_tests(ref):
    n = 0
    for path in git('ls-tree', '-r', '--name-only', ref).splitlines():
        if re.search(r'(^|/)(tests?|__tests__)/|\.(test|spec)\.[cm]?[jt]sx?$|(^|/)test_[^/]*\.py$', path):
            n += len(TEST_DEF.findall(git('show', f'{ref}:{path}', check=False)))
    return n


def check_test_count(base, head, r):
    before, after = count_tests(base), count_tests(head)
    if after < before:
        r.fail('試験の数が減った', '全体', f'{before} → {after}')


def check_package_json(base, head, path, r):
    for line in removed_lines(base, head, path):
        if PKG_GUARDED.search(line):
            r.fail('守りの設定を弱めた', path, f'消えた行: {line.strip()[:80]}')


def check_protected(base, head, r):
    for status, old, new in changed_files(base, head):
        path = new if status != 'D' else old
        if path.endswith('package.json'):
            check_package_json(base, head, path, r)
            continue
        if not PROTECTED.search(path):
            continue
        if status == 'D':
            r.fail('守りの設定を消した', path, 'ファイルごと消えた')
            continue
        for line in removed_lines(base, head, path):
            if line.strip():
                r.fail('守りの設定を弱めた', path, f'消えた行: {line.strip()[:80]}')
        for _p, line in added_lines(base, head, path):
            if WEAKEN.search(line):
                r.fail('守りの設定を弱めた', path, f'弱める語の行: {line.strip()[:80]}')


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='')
    ap.add_argument('--head', default='HEAD')
    ap.add_argument('--today')
    a = ap.parse_args(argv)
    r = Report('抜け道の封じ')
    today = datetime.date.fromisoformat(a.today) if a.today else datetime.date.today()
    allow = load_json(ALLOW, [])
    check_allow(allow, today, r)
    if has_base(a.base):
        check_suppressions(a.base, a.head, allow, r)
        check_append_only(a.base, a.head, r)
        check_test_count(a.base, a.head, r)
        check_protected(a.base, a.head, r)
    else:
        print('取り込み先が無い(最初の取り込み)。差分の検査は飛ばさず、許しの一覧だけ見た')
    return r.finish()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
