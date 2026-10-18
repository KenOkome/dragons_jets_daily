#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
まいすぽ 自動生成スクリプト (generate_news.py)
中日ドラゴンズ、千葉ジェッツふなばし、モータースポーツ、世界のメジャースポーツの
最新ニュースを収集し、3行要約カード ＆ 過去1週間のAI調査分析レポートを生成して
docs/index.html および docs/data/archive/YYYY-MM-DD.json, docs/data/index.json に出力します。
"""

import os
import sys
import json
import re
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

# 日本時間 (JST)
JST = timezone(timedelta(hours=9))

CATEGORIES = [
    {
        "id": "dragons",
        "name": "中日ドラゴンズ",
        "query": "(\"中日ドラゴンズ\" OR \"ドラゴンズ\") (試合 OR 勝 OR 敗 OR 選手 OR 監督 OR 工藤 OR 井上 OR ドラフト OR 契約更改 OR キャンプ OR 補強 OR 移籍 OR 現役ドラフト OR FA OR 戦力外 OR 自主トレ OR オープン戦 OR 成績) when:7d",
        "icon": "🐉",
        "desc": "試合結果速報、選手活躍、采配動向、チーム再建の要約まとめ"
    },
    {
        "id": "jets",
        "name": "千葉ジェッツふなばし",
        "query": "(\"千葉ジェッツ\" OR \"千葉ジェッツふなばし\" OR \"富樫勇樹\" OR \"渡邊雄太\" OR \"原修太\") (試合 OR 勝利 OR 敗戦 OR Bリーグ OR Bプレミア OR 節 OR 天皇杯 OR CS OR チャンピオンシップ OR 開幕 OR 移籍 OR バスケ) when:7d",
        "icon": "✈️",
        "desc": "Bリーグプレミア、試合速報、富樫・渡邊ら注目選手動向"
    },
    {
        "id": "motorsport",
        "name": "モータースポーツ",
        "query": "(F1 OR MotoGP OR 角田裕毅 OR 小椋藍 OR ホンダF1 OR WRC OR WEC OR インディカー) (GP OR 決勝 OR 予選 OR 表彰台 OR 参戦 OR 結果 OR レース) when:7d",
        "icon": "🏎️",
        "desc": "F1、MotoGPを中心にWRC、WEC、Indy等の日本勢＆世界トップレース要約"
    },
    {
        "id": "world",
        "name": "世界のメジャースポーツ",
        "query": "(MLB OR \"大谷翔平\" OR \"山本由伸\" OR プレミアリーグ OR チャンピオンズリーグ OR \"三笘薫\" OR \"久保建英\" OR NBA OR \"八村塁\" OR ワールドシリーズ OR ポストシーズン) (速報 OR 試合 OR 結果 OR ホームラン OR ゴール OR 勝利 OR 決勝 OR プレーオフ) when:7d",
        "icon": "🌍",
        "desc": "MLB（大谷・山本等）、欧州サッカー（三笘・久保等）、NBA等の注目速報要約"
    }
]

GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest"
]

def load_api_key():
    """環境変数または .env ファイルから API キーを取得"""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_paths = [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "exam_news_daily", ".env")
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            return line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass
    return ""

def strip_html_tags(text):
    """HTMLタグを除去しプレーンテキスト化"""
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", " ", text)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_for_similarity(title):
    """類似度判定用に記号・括弧・空白を除去して正規化"""
    s = re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", title)
    s = re.sub(r"[\s\W_]+", "", s)
    return s.lower()

def char_bigrams(text):
    """2文字N-gram集合を生成"""
    s = normalize_for_similarity(title=text)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i+2] for i in range(len(s) - 1)}

def is_duplicate_topic(title, selected_titles, threshold=0.34):
    """既存の選択済み記事と同一トピック（2-gram Jaccard類似度 >= threshold）か判定"""
    bg1 = char_bigrams(title)
    if not bg1:
        return False
    for prev in selected_titles:
        bg2 = char_bigrams(prev)
        if not bg2:
            continue
        inter = len(bg1 & bg2)
        union = len(bg1 | bg2)
        if union > 0 and (inter / union) >= threshold:
            return True
    return False

def is_relevant_article(clean_title, snippet, category_id):
    """カテゴリ無関係の記事（例：中日スポーツ配信のMLB単体記事等）を除外"""
    combined = f"{clean_title} {snippet}"
    if category_id == "dragons":
        dragons_keywords = [
            "中日", "ドラゴンズ", "工藤", "井上", "立浪", "バンテリン", "ナゴヤ",
            "髙橋宏斗", "高橋宏斗", "大野", "松山", "細川", "村松", "石川昂",
            "根尾", "金丸", "森駿太", "清水", "柳", "福永", "岡林", "涌井", "宏斗", "竜"
        ]
        # タイトル自体にドラゴンズ関連ワードが1つも含まれない場合は他球団・MLB記事とみなして除外
        if not any(k in clean_title for k in dragons_keywords):
            return False
        # セ・リーグ順位表まとめ等で他球団メインの記事を抑制
        if "順位表" in clean_title and not clean_title.startswith(("【中日", "中日", "ドラゴンズ")):
            return False
    elif category_id == "jets":
        jets_keywords = [
            "ジェッツ", "千葉J", "富樫", "渡邊雄太", "原修太", "金近", "小川",
            "ホグ", "ムーニー", "船橋", "LaLa arena", "ららアリーナ", "Bリーグ", "B.LEAGUE", "Bプレミア"
        ]
        if not any(k in combined for k in jets_keywords):
            return False
    return True

def parse_pub_datetime(pub_date_str):
    """RFC 2822 文字列を日本時間の datetime オブジェクトに変換"""
    if not pub_date_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(JST)
    except Exception:
        try:
            dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.replace(tzinfo=timezone.utc).astimezone(JST)
        except Exception:
            return None

def score_article(title, age_hours):
    """鮮度（公開からの経過時間）＋ 見出しの具体性・情報量を複合スコアリング"""
    score = 0.0
    # 1. 鮮度スコア（最新ニュースを最優先）
    if age_hours <= 18:
        score += 14.0
    elif age_hours <= 36:
        score += 10.0
    elif age_hours <= 72:
        score += 6.0
    elif age_hours <= 120:
        score += 3.0
    else:
        score += 1.0

    # 2. 具体性スコア（カギ括弧の発言、数字、重要キーワード）
    if "「" in title and "」" in title:
        score += 4.0
    if re.search(r"\d+", title):
        score += 2.0
    if any(w in title for w in [
        "工藤", "井上", "髙橋宏斗", "高橋宏斗", "細川", "松山", "村松", "金丸", "根尾",
        "富樫", "渡邊雄太", "原修太", "角田", "ホンダ", "小椋", "中上", "勝田", "F1", "MotoGP",
        "大谷", "山本由伸", "三笘", "久保", "八村", "ドジャース"
    ]):
        score += 3.0
    if any(w in title for w in [
        "勝利", "快勝", "逆転", "本塁打", "ホームラン", "ゴール", "優勝", "表彰台",
        "決定", "就任", "ドラフト", "契約", "開幕", "連勝", "新記録", "圧巻", "劇的"
    ]):
        score += 2.5
    return score

def fetch_rss_news(category_id, query, max_items=6):
    """Google News RSS から最新ニュースを取得し、期間フィルタ＆重複排除して厳選"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
    )
    
    now_jst = datetime.now(JST)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            
            raw_candidates = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_str = item.findtext("pubDate", "").strip()
                desc_raw = item.findtext("description", "").strip()
                source_elem = item.find("source")
                source = source_elem.text.strip() if source_elem is not None and source_elem.text else "スポーツ速報"
                
                clean_title = re.sub(r"\s*[-|]\s*[^-|]+$", "", title).strip()
                snippet = strip_html_tags(desc_raw)
                # スニペットからタイトル重複や配信元名を軽く整理
                if snippet.startswith(clean_title):
                    snippet = snippet[len(clean_title):].strip(" -|　")
                
                if not is_relevant_article(clean_title, snippet, category_id):
                    continue
                
                pub_dt = parse_pub_datetime(pub_date_str)
                if pub_dt is not None:
                    age_hours = max(0.0, (now_jst - pub_dt).total_seconds() / 3600.0)
                    # 10日（240時間）より古い記事は完全に除外（5月〜8月の古い記事混入を遮断）
                    if age_hours > 240.0:
                        continue
                    pub_date_display = pub_dt.strftime("%m/%d %H:%M")
                    is_new = (age_hours <= 28.0)
                else:
                    age_hours = 48.0
                    pub_date_display = "最新速報"
                    is_new = False

                score = score_article(clean_title, age_hours)
                
                raw_candidates.append({
                    "title": clean_title,
                    "raw_title": title,
                    "snippet": snippet[:220],
                    "link": link,
                    "pub_date": pub_date_display,
                    "age_hours": age_hours,
                    "is_new": is_new,
                    "source": source,
                    "score": score,
                    "headline": "",
                    "points": [],
                    "takeaway": ""
                })
            
            # 複合スコア（鮮度＋具体性）の高い順にソート
            raw_candidates.sort(key=lambda x: x["score"], reverse=True)
            
            selected_items = []
            selected_titles = []
            
            for cand in raw_candidates:
                if not is_duplicate_topic(cand["title"], selected_titles):
                    selected_titles.append(cand["title"])
                    selected_items.append(cand)
                if len(selected_items) >= max_items:
                    break
            
            # 画面上では新しい順が見やすいため、選択された上位記事を公開日時（新しい順）に整列
            selected_items.sort(key=lambda x: x["age_hours"])
            return selected_items
    except Exception as e:
        print(f"RSS取得エラー ({category_id}): {e}", file=sys.stderr)
        return []

def clean_takeaway_text(text):
    """AI出力のtakeaway先頭に重複しやすい『💡 注目:』等を除去"""
    if not text:
        return ""
    t = str(text).strip()
    t = re.sub(r"^[📣💡\s]*注目(?:ポイント)?[:：]?\s*", "", t)
    t = re.sub(r"^[📣💡\s]*注目(?:ポイント)?[:：]?\s*", "", t)
    return t.strip()

def sanitize_url(url):
    """http/https スキームのみ許可し、安全なエスケープ済みURLを返す"""
    if not url:
        return "#"
    u = str(url).strip()
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme not in ("http", "https"):
        return "#"
    return html.escape(u, quote=True)

def load_recent_archive_headlines(script_dir, category_id, days=7):
    """過去7日分のアーカイブJSONから主要ニュース見出しを取得し、1週間レポートの文脈を補強"""
    archive_dir = os.path.join(script_dir, "docs", "data", "archive")
    if not os.path.exists(archive_dir):
        return []
    files = sorted([f for f in os.listdir(archive_dir) if f.endswith(".json")], reverse=True)[:days]
    past_lines = []
    seen = set()
    for fname in files:
        fpath = os.path.join(archive_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            cat_data = data.get("categories", {}).get(category_id, {})
            for n in cat_data.get("news", [])[:3]:
                ttl = n.get("title", "").strip()
                if ttl and ttl not in seen:
                    seen.add(ttl)
                    past_lines.append(f"- [{data.get('date', '')[5:]}] {ttl}")
        except Exception:
            continue
    return past_lines[:12]

def call_gemini_json(prompt, api_key, timeout=30):
    """Gemini API を呼び出して JSON をパースして返す（エラーログ・リトライ対応）"""
    if not api_key:
        return None, None
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.25}
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                try:
                    return json.loads(text), model
                except json.JSONDecodeError:
                    m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
                    if m:
                        return json.loads(m.group(1)), model
        except urllib.error.HTTPError as he:
            print(f"  [Gemini HTTP {he.code}] model={model}", file=sys.stderr)
            if he.code == 429:
                time.sleep(2)
            continue
        except Exception as e:
            print(f"  [Gemini Error] model={model}: {e}", file=sys.stderr)
            continue
    return None, None

# ==============================================================================
# 過去1週間のAI調査・深掘りレポート生成
# ==============================================================================
def generate_weekly_ai_report(category_id, category_name, news_items, api_key, script_dir):
    """過去1週間のニュースとアーカイブ履歴を横断的に分析した深掘りレポートを生成"""
    if not news_items:
        return "", None
    
    current_articles_text = "\n".join([
        f"- [{item['pub_date']}] {item['title']} ({item['source']})"
        + (f" / 概要: {item['snippet']}" if item.get("snippet") else "")
        for item in news_items
    ])
    past_lines = load_recent_archive_headlines(script_dir, category_id, days=7)
    past_context = "\n".join(past_lines) if past_lines else "（直近取得記事を参照）"
    
    if api_key:
        prompt = f"""あなたは「{category_name}」を専門に取材・分析しているスポーツアナリストです。
本日の最新ニュースおよび直近1週間のアーカイブ見出しをもとに、ファンが今一番知りたい【過去1週間の徹底調査レポート】を作成してください。

【本日の最新ニュース】
{current_articles_text}

【直近1週間の主な出来事（時系列アーカイブ）】
{past_context}

【厳守ルール】
1. 与えられた記事見出し・概要に含まれる事実のみに基づいて分析し、記事にないスコアや順位、発言を勝手に創作（ハルシネーション）しないでください。
2. 以下のJSONオブジェクト形式のみで出力してください：
{{
  "title": "1週間の総括見出し（35文字以内。最新の重要トピックを端的に）",
  "summary": "直近1週間の戦況・チーム動向の総括（90〜150文字程度）",
  "key_players": "注目選手・キーマン・首脳陣の動き（80〜140文字程度）",
  "outlook": "今後の展望とファンが注目すべき見どころ（80〜140文字程度）"
}}"""
        parsed, used_model = call_gemini_json(prompt, api_key)
        if isinstance(parsed, dict) and parsed.get("title"):
            now_str = datetime.now(JST).strftime("%m/%d %H:%M")
            report_obj = {
                "analyzed_at": now_str,
                "title": str(parsed.get("title", "")).strip(),
                "summary": str(parsed.get("summary", "")).strip(),
                "key_players": str(parsed.get("key_players", "")).strip(),
                "outlook": str(parsed.get("outlook", "")).strip()
            }
            print(f"  -> [{category_name}] 過去1週間AI調査レポート生成完了 ({used_model})")
            return render_report_html(category_id, report_obj), report_obj

    # 動的フォールバック（固定の9月イベントではなく、現在の取得記事から合成）
    return fallback_weekly_report(category_id, category_name, news_items)

def fallback_weekly_report(category_id, category_name, news_items):
    """API未接続時でも現在の記事見出し群から安全に調査レポートを合成"""
    now_str = datetime.now(JST).strftime("%m/%d %H:%M")
    top_titles = [re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", item["title"]) for item in news_items[:3]]
    lead_topic = top_titles[0][:32] if top_titles else f"{category_name} 最新動向総括"
    joined_topics = " / ".join([t[:28] for t in top_titles])

    report_obj = {
        "analyzed_at": now_str,
        "title": f"{lead_topic}",
        "summary": f"直近の{category_name}では、「{joined_topics}」など注目のニュースが相次いで報じられています。",
        "key_players": "主力選手や首脳陣の最新コメント、チーム編成・次戦に向けた調整状況に高い関心が集まっています。",
        "outlook": "今後の試合日程やチーム戦略の展開に向け、各メディアの続報と選手のパフォーマンスに注目です。"
    }
    return render_report_html(category_id, report_obj), report_obj

def render_report_html(category_id, r):
    """調査レポートのHTMLをレンダリング（開閉可能なアコーディオン対応＆XSSエスケープ済）"""
    if not r:
        return ""
    now_str = html.escape(str(r.get("analyzed_at", datetime.now(JST).strftime("%m/%d %H:%M"))), quote=True)
    title = html.escape(str(r.get("title", "")), quote=True)
    summary = html.escape(str(r.get("summary", "")), quote=True)
    key_players = html.escape(str(r.get("key_players", "")), quote=True)
    outlook = html.escape(str(r.get("outlook", "")), quote=True)
    cat_icon = "⚾" if category_id == "dragons" else ("🏀" if category_id == "jets" else ("🏎️" if category_id == "motorsport" else "🌍"))

    return f"""
    <details class="report-card {category_id}" open>
        <summary class="report-summary-toggle">
            <div class="report-header">
                <span class="report-badge">📊 過去1週間のAI調査レポート</span>
                <span class="report-header-right">
                    <span class="report-date">{now_str} AI分析</span>
                    <span class="report-chevron" aria-hidden="true">▾</span>
                </span>
            </div>
            <h3 class="report-title">{title}</h3>
        </summary>
        <div class="report-body">
            <div class="report-section">
                <div class="report-section-title">{cat_icon} <strong>直近1週間の戦況・動向総括</strong></div>
                <div class="report-section-text">{summary}</div>
            </div>
            <div class="report-section">
                <div class="report-section-title">🌟 <strong>注目選手・キーマンの動き</strong></div>
                <div class="report-section-text">{key_players}</div>
            </div>
            <div class="report-section">
                <div class="report-section-title">🔮 <strong>今後の展望と注目ポイント</strong></div>
                <div class="report-section-text">{outlook}</div>
            </div>
        </div>
    </details>
    """

# ==============================================================================
# 各ニュースの3行要約生成
# ==============================================================================
def summarize_news_items(category_id, category_name, news_items, api_key):
    """各ニュース記事の3行要約を生成"""
    if not news_items:
        return []
    
    # まず記事自身のタイトル・スニペットから安全な初期要約をセット（欠落防止）
    news_items = fallback_smart_summaries(category_id, category_name, news_items)
    if not api_key:
        return news_items
    
    articles_text = "\n\n".join([
        f"【記事{i+1}】\n公開日時: {item['pub_date']}\n見出し: {item['title']}\n配信元: {item['source']}"
        + (f"\n抜粋: {item['snippet']}" if item.get("snippet") else "")
        for i, item in enumerate(news_items)
    ])
    
    total_count = len(news_items)
    prompt = f"""あなたは「{category_name}」を専門に取材・解説するプロのスポーツ記者です。
以下の最新ニュース全{total_count}件を分析し、ファンが30秒で核心を把握できる3行要約を作成してください。

【対象記事】
{articles_text}

【最重要ルール（厳守）】
1. **対象記事全{total_count}件（index: 1 〜 {total_count}）すべてについて、1件も漏らさず出力してください**。
2. **事実厳守（ハルシネーション禁止）**: 見出しと抜粋に書かれている事実のみを基に要約し、書かれていない試合スコアや発言を勝手に創作しないでください。
3. headline: 記事の結論・核心を30文字以内で端的に記述してください。
4. points: 具体的な事実・背景・今後の影響を3点（各35〜65文字程度）で整理してください。
5. takeaway: ファン目線での注目ポイントや見どころを40〜65文字程度で記述してください（※先頭に「注目:」や「💡」は付けないでください）。

【出力JSON配列フォーマット】
[
  {{
    "index": 1,
    "headline": "何が起きたかの結論（30文字以内）",
    "points": [
      "具体的な事実・発言内容（35〜65文字）",
      "その背景やチーム・戦況における意味（35〜65文字）",
      "今後の展開への影響（35〜65文字）"
    ],
    "takeaway": "ファン目線での具体的な見どころ（40〜65文字）"
  }}
]"""

    parsed, used_model = call_gemini_json(prompt, api_key)
    if isinstance(parsed, list):
        for s in parsed:
            if not isinstance(s, dict):
                continue
            idx = s.get("index", 1) - 1
            if 0 <= idx < len(news_items):
                if s.get("headline"):
                    news_items[idx]["headline"] = str(s.get("headline", "")).strip()
                if s.get("points") and isinstance(s.get("points"), list):
                    news_items[idx]["points"] = [str(p).strip() for p in s.get("points") if str(p).strip()][:3]
                if s.get("takeaway"):
                    news_items[idx]["takeaway"] = clean_takeaway_text(s.get("takeaway", ""))
        print(f"  -> [{category_name}] Gemini API ({used_model}) による要約生成成功！")
        return news_items

    print(f"  -> [{category_name}] 動的フォールバック要約を使用しました。")
    return news_items

def fallback_smart_summaries(category_id, category_name, news_items):
    """API障害時でも過去の古い固定データを混ぜず、記事自身の見出し・抜粋・発言から安全に要約を構成"""
    for item in news_items:
        t = item["title"]
        src = item["source"]
        snippet = item.get("snippet", "")
        
        clean = re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", t)
        clean = re.sub(r"\s*[／｜|].*$", "", clean).strip()
        quotes = re.findall(r"「([^」]+)」", t)
        
        item["headline"] = clean[:30] if len(clean) > 30 else clean
        pts = [f"「{src}」より、{clean}に関する最新動向が報じられました。"]
        if quotes:
            pts.append(f"記事内では「{quotes[0]}」といった注目の発言・コメントが伝えられています。")
        elif snippet and snippet != clean:
            pts.append(f"詳細抜粋：{snippet[:60]}...")
        else:
            pts.append(f"{category_name}の今後のチーム状況や戦況に関わるトピックとして注目されています。")
        pts.append("最新の動向や続報はリンク先の元記事全文から確認できます。")
        
        item["points"] = pts
        item["takeaway"] = f"{category_name}の最新動向をチェックして次戦や今後の展開に注目しましょう！"
    return news_items

def render_news_cards(news_items):
    """ニュースカード群のHTMLを生成（XSSエスケープ・NEWバッジ・重複防止対応）"""
    if not news_items:
        return """
        <div class="empty-state">
            <div class="icon">📭</div>
            <p>本日の新着ニュースはまだありません。<br>最新情報が入り次第自動更新されます。</p>
        </div>
        """
    
    cards_html = []
    for item in news_items:
        title_esc = html.escape(str(item.get("title", "")), quote=True)
        source_esc = html.escape(str(item.get("source", "")), quote=True)
        pub_date_esc = html.escape(str(item.get("pub_date", "")), quote=True)
        headline_esc = html.escape(str(item.get("headline", item.get("title", ""))), quote=True)
        link_esc = sanitize_url(item.get("link", "#"))
        is_new = bool(item.get("is_new", False))
        
        points = item.get("points", [])
        points_html = "".join([
            f'<div class="summary-point"><span class="dot">•</span><span>{html.escape(str(p), quote=True)}</span></div>'
            for p in points
        ])
        
        takeaway_clean = clean_takeaway_text(item.get("takeaway", ""))
        takeaway_esc = html.escape(takeaway_clean, quote=True)
        takeaway_html = f'<div class="summary-takeaway">📣 <strong>注目:</strong> {takeaway_esc}</div>' if takeaway_esc else ""
        
        new_badge_html = '<span class="badge-new">NEW</span>' if is_new else ""
        card_new_class = " is-new" if is_new else ""
        
        card = f"""
        <article class="news-card{card_new_class}" data-url="{link_esc}">
            <div class="card-header">
                <div class="card-meta-left">
                    {new_badge_html}
                    <span class="card-source">{source_esc}</span>
                </div>
                <span class="card-date">{pub_date_esc}</span>
            </div>
            <h3 class="card-title">{title_esc}</h3>
            <div class="summary-box">
                <div class="summary-headline"><span class="headline-badge">📌 要約</span> {headline_esc}</div>
                <div class="summary-points">
                    {points_html}
                </div>
                {takeaway_html}
            </div>
            <div class="card-footer">
                <a href="{link_esc}" target="_blank" rel="noopener noreferrer" class="btn-read-more">
                    <span>元記事を読む</span>
                    <span>↗</span>
                </a>
            </div>
        </article>
        """
        cards_html.append(card)
    return "\n".join(cards_html)

def save_daily_archive(script_dir, now_jst, updated_str, all_news, ai_report_objs):
    """本日のデータを docs/data/archive/YYYY-MM-DD.json に保存し、docs/data/index.json を更新"""
    archive_dir = os.path.join(script_dir, "docs", "data", "archive")
    index_path = os.path.join(script_dir, "docs", "data", "index.json")
    os.makedirs(archive_dir, exist_ok=True)
    
    date_key = now_jst.strftime("%Y-%m-%d")
    categories_payload = {}
    for cat in CATEGORIES:
        cid = cat["id"]
        clean_news = []
        for n in all_news.get(cid, []):
            clean_news.append({
                "title": n.get("title", ""),
                "source": n.get("source", ""),
                "pub_date": n.get("pub_date", ""),
                "link": n.get("link", "#"),
                "headline": n.get("headline", ""),
                "points": n.get("points", []),
                "takeaway": clean_takeaway_text(n.get("takeaway", "")),
                "is_new": bool(n.get("is_new", False))
            })
        categories_payload[cid] = {
            "report": ai_report_objs.get(cid),
            "news": clean_news
        }
        
    daily_payload = {
        "date": date_key,
        "updated_at": updated_str,
        "categories": categories_payload
    }
    
    daily_file = os.path.join(archive_dir, f"{date_key}.json")
    with open(daily_file, "w", encoding="utf-8") as f:
        json.dump(daily_payload, f, ensure_ascii=False, indent=2)
        
    # 全アーカイブJSONを走査して index.json を再構築
    all_files = sorted([f[:-5] for f in os.listdir(archive_dir) if re.match(r"^\d{4}-\d{2}-\d{2}\.json$", f)], reverse=True)
    index_entries = []
    for d in all_files:
        fpath = os.path.join(archive_dir, f"{d}.json")
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                rec = json.load(f)
            dragons_title = ""
            if "dragons" in rec.get("categories", {}) and rec["categories"]["dragons"].get("report"):
                dragons_title = rec["categories"]["dragons"]["report"].get("title", "")
            index_entries.append({
                "date": d,
                "updated_at": rec.get("updated_at", ""),
                "label": f"{int(d[5:7])}/{int(d[8:10])}",
                "summary_title": dragons_title
            })
        except Exception:
            continue
            
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump({
            "latest_date": all_files[0] if all_files else date_key,
            "total_days": len(index_entries),
            "dates": index_entries
        }, f, ensure_ascii=False, indent=2)
    print(f"=== アーカイブ保存完了: {daily_file} (全 {len(index_entries)} 日分) ===")

# ==============================================================================
# メイン処理
# ==============================================================================
def main():
    print("=== まいすぽ 生成開始 ===")
    api_key = load_api_key()
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(script_dir, "template.html")
    output_path = os.path.join(script_dir, "docs", "index.html")
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
        
    all_news = {}
    ai_reports_html = {}
    ai_report_objs = {}
    total_fetched = 0
    
    for cat in CATEGORIES:
        cid = cat["id"]
        cname = cat["name"]
        print(f"[{cname}] ニュース取得中...")
        items = fetch_rss_news(cid, cat["query"], max_items=6)
        print(f"  -> {len(items)} 件取得。")
        total_fetched += len(items)
        
        # 1. 過去1週間のAI調査レポート生成
        print(f"  -> 過去1週間のAI調査レポート生成中...")
        report_html, report_obj = generate_weekly_ai_report(cid, cname, items, api_key, script_dir)
        ai_reports_html[cid] = report_html
        ai_report_objs[cid] = report_obj
        time.sleep(1)
        
        # 2. 各記事の3行要約生成
        print(f"  -> 各記事の3行要約生成中...")
        summarized_items = summarize_news_items(cid, cname, items, api_key)
        all_news[cid] = summarized_items
        time.sleep(1)
        
    # 全カテゴリ合計0件の場合はネットワーク障害とみなし、既存の index.html を白紙上書きしないよう異常終了
    if total_fetched == 0:
        print("エラー: 全カテゴリのニュース取得件数が0件のため更新を中断します。", file=sys.stderr)
        sys.exit(1)
        
    now_jst = datetime.now(JST)
    updated_str = now_jst.strftime("%m月%d日 %H:%M")
    
    # 日別アーカイブJSONと index.json を保存
    save_daily_archive(script_dir, now_jst, updated_str, all_news, ai_report_objs)
    
    rendered = template
    rendered = rendered.replace("{{UPDATED_TIME}}", updated_str)
    rendered = rendered.replace("{{CURRENT_YEAR}}", str(now_jst.year))
    
    rendered = rendered.replace("{{DRAGONS_COUNT}}", str(len(all_news.get("dragons", []))))
    rendered = rendered.replace("{{JETS_COUNT}}", str(len(all_news.get("jets", []))))
    rendered = rendered.replace("{{MOTORSPORT_COUNT}}", str(len(all_news.get("motorsport", []))))
    rendered = rendered.replace("{{WORLD_COUNT}}", str(len(all_news.get("world", []))))
    
    rendered = rendered.replace("{{DRAGONS_AI_REPORT}}", ai_reports_html.get("dragons", ""))
    rendered = rendered.replace("{{JETS_AI_REPORT}}", ai_reports_html.get("jets", ""))
    rendered = rendered.replace("{{MOTORSPORT_AI_REPORT}}", ai_reports_html.get("motorsport", ""))
    rendered = rendered.replace("{{WORLD_AI_REPORT}}", ai_reports_html.get("world", ""))
    
    rendered = rendered.replace("{{DRAGONS_NEWS_CARDS}}", render_news_cards(all_news.get("dragons", [])))
    rendered = rendered.replace("{{JETS_NEWS_CARDS}}", render_news_cards(all_news.get("jets", [])))
    rendered = rendered.replace("{{MOTORSPORT_NEWS_CARDS}}", render_news_cards(all_news.get("motorsport", [])))
    rendered = rendered.replace("{{WORLD_NEWS_CARDS}}", render_news_cards(all_news.get("world", [])))
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
        
    print(f"=== 生成完了: {output_path} ===")

if __name__ == "__main__":
    main()
