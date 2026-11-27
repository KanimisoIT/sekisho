#!/usr/bin/env python3
"""経緯の注釈を止める。足された注釈の行に、昔の経緯(「以前は」「修正」「〜のため追加」、日付など)が書かれていたら赤。

注釈は「次に読む AI への悪い手本」になりやすい(Lauren Tan の講演)。今の作りの説明だけを残す。
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Report, added_lines, has_base

CODE = re.compile(r'\.(?:[cm]?[jt]sx?|py|ps1|sh|css|scss|html|vue|svelte)$')
COMMENT = re.compile(r'^\s*(?://|#(?!!)|/\*|\*|<!--)|\s(?://|#)\s')
HISTORY = re.compile(r'以前は|前は|修正し|直した|追加した|のため追加|変更した|に変えた|旧版|版から|'
                     r'\bfix(?:ed|es)?\b|\bpreviously\b|\bused to\b|\bwas changed\b|\bchanged from\b|\bworkaround for\b|'
                     r'20\d\d-\d\d-\d\d|\b\d{1,2}/\d{1,2}\b', re.I)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='')
    ap.add_argument('--head', default='HEAD')
    a = ap.parse_args(argv)
    r = Report('経緯の注釈')
    if not has_base(a.base):
        print('取り込み先が無い(最初の取り込み)')
        return r.finish()
    for path, line in added_lines(a.base, a.head):
        if CODE.search(path) and not path.startswith('.sekisho/') and COMMENT.search(line) and HISTORY.search(line):
            r.fail('経緯の注釈', path, line.strip()[:80])
    return r.finish()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
