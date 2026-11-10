#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""まいすぽ スロット完全性・品質テスト（全タブきっかり6枠＝計24枠検証）"""
import os, sys, json, re
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_DIR = os.path.join(SCRIPT_DIR, "docs", "data", "archive")
HTML_PATH = os.path.join(SCRIPT_DIR, "docs", "index.html")

def test_slots():
    print("=== [QA Test] まいすぽ スロット完全性テスト開始 ===")
    json_files = sorted([f for f in os.listdir(ARCHIVE_DIR) if f.endswith(".json")], reverse=True)
    if not json_files:
        sys.exit("❌ FAIL: アーカイブJSONが存在しません")
    with open(os.path.join(ARCHIVE_DIR, json_files[0]), "r", encoding="utf-8") as f:
        data = json.load(f)

    categories = data.get("categories", {})
    expected = ["dragons", "jets", "motorsport", "world"]
    total = 0
    errors = []

    for cid in expected:
        news = categories.get(cid, {}).get("news", [])
        cnt = len(news)
        total += cnt
        if cnt != 6:
            errors.append(f"{cid} の記事数が {cnt} 件（期待値: 6件）")
        if cid in ("dragons", "jets"):
            t_cnt = sum(1 for n in news if n.get("sub_type") == "team")
            l_cnt = sum(1 for n in news if n.get("sub_type") == "league")
            if t_cnt != 4 or l_cnt != 2:
                errors.append(f"{cid} 内訳不正: team={t_cnt}(期待4), league={l_cnt}(期待2)")
        elif cid == "world":
            u_cnt = sum(1 for n in news if n.get("sub_type") == "unique")
            if u_cnt != 1:
                errors.append(f"world 地域熱狂ユニーク枠が {u_cnt} 件（期待1）")

    if total != 24:
        errors.append(f"全タブ合計記事数が {total} 件（期待値: 24件）")

    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    cards = len(re.findall(r'<article class="[^"]*news-card', html))
    if cards != 24:
        errors.append(f"HTML内のnews-card数が {cards} 件（期待値: 24件）")

    if errors:
        sys.exit("❌ テスト失敗:\n" + "\n".join("  - " + e for e in errors))
    print("✅ [ALL PASS] 全タブきっかり6枠（計24枠）およびスロット内訳の完全一致を確認しました！")

if __name__ == "__main__":
    test_slots()
