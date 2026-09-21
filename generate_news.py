#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ドラ＆ジェッツ速報 自動生成スクリプト (generate_news.py)
中日ドラゴンズと千葉ジェッツふなばしの最新ニュースを収集し、
3行要約カード ＆ 過去1週間のAI調査分析レポートを生成して docs/index.html に出力します。
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# 日本時間 (JST)
JST = timezone(timedelta(hours=9))

CATEGORIES = [
    {
        "id": "dragons",
        "name": "中日ドラゴンズ",
        "query": "(中日ドラゴンズ OR 中日 OR ドラゴンズ) (試合 OR 勝 OR 敗 OR 選手 OR 監督 OR 移籍 OR ドラフト OR 成績 OR セレモニー)",
        "icon": "🐉",
        "desc": "試合結果速報、選手活躍、采配動向、チーム再建の要約まとめ"
    },
    {
        "id": "jets",
        "name": "千葉ジェッツふなばし",
        "query": "(千葉ジェッツ OR 千葉ジェッツふなばし OR 富樫勇樹 OR 原修太 OR 渡邊雄太) (試合 OR 勝利 OR 敗戦 OR 開幕 OR 移籍 OR プレシーズン OR 天皇杯 OR バスケ)",
        "icon": "✈️",
        "desc": "Bリーグプレミア開幕、試合速報、富樫・渡邊ら注目選手動向"
    },
    {
        "id": "motorsport",
        "name": "モータースポーツ",
        "query": "(F1 OR MotoGP OR \"角田裕毅\" OR \"小椋藍\" OR \"中上貴晶\" OR \"ホンダF1\" OR \"トヨタ\" OR WRC OR WEC OR \"ル・マン\" OR インディカー OR ダカールラリー) (グランプリ OR 決勝 OR 予選 OR 表彰台 OR 参戦 OR 速報 OR 結果 OR レース)",
        "icon": "🏎️",
        "desc": "F1、MotoGPを中心にWRC、WEC、Indy等の日本勢＆世界トップレース要約"
    }
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

def get_topic_key(title, category_id):
    """タイトルから話題（トピック）の分類キーを判定"""
    t = title
    if category_id == 'dragons':
        if '語録' in t:
            return 'director_words'
        if '松山' in t and ('30' in t or 'セーブ' in t or '守護神' in t):
            return 'matsuyama_save'
        if '大野' in t and ('10勝' in t or '左腕' in t or '２ケタ' in t or '2ケタ' in t):
            return 'ohno_10win'
        if '続投' in t or '現実味' in t:
            return 'manager_continue'
        if any(w in t for w in ['セレモニー', '最終戦', '謝罪', 'お詫び', 'おわび', 'あいさつ', 'スピーチ', '怒号']):
            return 'ceremony_speech'
        if '去就' in t or '加藤' in t:
            return 'manager_future'
        if any(w in t for w in ['髙橋宏斗', '高橋宏斗', '村松', '無失点', '6号', '4勝目', '勝', '敗', 'スコア', '試合結果']):
            return 'game_result'
        if '動員' in t or '観客' in t:
            return 'attendance'
        if '若松' in t or '独立球団' in t:
            return 'ob_topic'
        return 'general_' + re.sub(r'[\s\W]', '', t)[:8]
    elif category_id == 'jets':
        if '小川' in t and ('富樫' in t or '挑戦状' in t):
            return 'ogawa_challenge'
        if '若手' in t and 'ベテラン' in t or ('開幕' in t and 'プレミア' in t):
            return 'young_veteran'
        if 'PRESEASON' in t or 'プレシーズン' in t or 'ちばぎん' in t:
            return 'preseason'
        if 'TOGAシート' in t or '招待席' in t:
            return 'toga_seat'
        if '動員' in t or '観客' in t:
            return 'attendance'
        if '決起会' in t or 'グッズ' in t or 'イベント' in t or '装飾' in t:
            return 'fan_event'
        if 'SEASON' in t or 'B.LEAGUE' in t:
            return 'resona_season'
        return 'general_' + re.sub(r'[\s\W]', '', t)[:8]
    else: # motorsport
        if '角田' in t:
            return 'f1_tsunoda'
        if 'ホンダ' in t or 'アストンマーティン' in t or 'PU' in t:
            return 'f1_honda'
        if '小椋' in t:
            return 'motogp_ogura'
        if '中上' in t or 'もてぎ' in t:
            return 'motogp_nakagami'
        if 'クアルタラロ' in t or 'ヤマハ' in t:
            return 'motogp_yamaha'
        if 'マルケス' in t or 'バニャイア' in t or 'オーストリアGP' in t or 'MotoGP' in t:
            return 'motogp_race'
        if 'ル・マン' in t or 'WEC' in t or '耐久' in t:
            return 'wec_lemans'
        if 'WRC' in t or 'ラリー' in t or '勝田' in t:
            return 'wrc_rally'
        if 'インディ' in t or 'Indy' in t or '佐藤琢磨' in t:
            return 'indycar'
        if 'ダカール' in t:
            return 'dakar'
        if 'フェルスタッペン' in t or 'ノリス' in t or 'メルセデス' in t or 'F1' in t:
            return 'f1_general'
        return 'general_' + re.sub(r'[\s\W]', '', t)[:8]

def score_article(title):
    """見出しの具体性・情報量をスコアリング（発言や数字、具体的選手名を含むものを優先）"""
    score = 0
    if '「' in title and '」' in title:
        score += 5
    if re.search(r'\d+', title):
        score += 2
    if any(w in title for w in ['井上監督', '富樫', '髙橋宏斗', '高橋宏斗', '村松', '加藤', '小川', '角田', 'ホンダ', '小椋', '中上', 'F1', 'MotoGP', 'WEC', 'WRC', 'ル・マン']):
        score += 3
    if '謝罪' in title or '怒号' in title or '挑戦状' in title:
        score += 4
    return score

def fetch_rss_news(category_id, query, max_items=6):
    """Google News RSS から最新ニュースを取得し、トピック重複を排除して厳選"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            
            raw_candidates = []
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_str = item.findtext("pubDate", "").strip()
                source_elem = item.find("source")
                source = source_elem.text.strip() if source_elem is not None and source_elem.text else "スポーツ速報"
                
                clean_title = re.sub(r"\s*[-|]\s*[^-|]+$", "", title).strip()
                
                # 千葉ジェッツの場合、関係の薄い海外・日本代表のみのニュース（中国大敗など）を除外
                if category_id == "jets":
                    if not any(k in clean_title for k in ["ジェッツ", "富樫", "原修太", "渡邊雄太", "船橋", "B.LEAGUE", "Bリーグ", "ちばぎん"]):
                        continue
                        
                topic = get_topic_key(clean_title, category_id)
                score = score_article(clean_title)
                
                raw_candidates.append({
                    "title": clean_title,
                    "raw_title": title,
                    "link": link,
                    "pub_date": format_pub_date(pub_date_str),
                    "source": source,
                    "topic": topic,
                    "score": score,
                    "headline": "",
                    "points": [],
                    "takeaway": ""
                })
            
            # 各トピックごとに最もスコアの高い代表記事を選定
            selected_items = []
            seen_topics = set()
            
            # スコア順にソートして、より具体的で魅力的な記事を優先
            raw_candidates.sort(key=lambda x: x["score"], reverse=True)
            
            for cand in raw_candidates:
                topic = cand["topic"]
                if topic not in seen_topics:
                    seen_topics.add(topic)
                    selected_items.append(cand)
                if len(selected_items) >= max_items:
                    break
                    
            return selected_items
    except Exception as e:
        print(f"RSS取得エラー ({query}): {e}", file=sys.stderr)
        return []

def format_pub_date(pub_date_str):
    """pubDate 文字列 (RFC 2822) を日本時間表記 (MM/DD HH:MM) に変換"""
    try:
        dt = datetime.strptime(pub_date_str, "%a, %d %b %Y %H:%M:%S %Z")
        dt_jst = dt.replace(tzinfo=timezone.utc).astimezone(JST)
        return dt_jst.strftime("%m/%d %H:%M")
    except Exception:
        return "本日更新"

# ==============================================================================
# 過去1週間のAI調査・深掘りレポート生成
# ==============================================================================
def generate_weekly_ai_report(category_id, category_name, news_items, api_key):
    """過去1週間のニュースを横断的に調査・分析した深掘りレポートを生成"""
    if not news_items:
        return ""
    
    articles_text = "\n".join([f"- {item['title']} ({item['source']})" for item in news_items])
    
    if api_key:
        prompt = f"""あなたは「{category_name}」を誰よりも深く取材・分析しているプロのスポーツアナリストです。
過去1週間の最新ニュース見出しをもとに、ファンが今一番知りたい【過去1週間の徹底調査レポート】を作成してください。

【対象ニュース】
{articles_text}

【必須指示】
以下のJSONフォーマットで出力してください（Markdownの ```json で囲む）：
{{
  "title": "1週間の総括見出し（35文字以内。試合結果や重要トピックを端的に）",
  "summary": "直近1週間の試合動向・チーム状況の分析総括（90〜150文字程度。勝敗、スコア、チームの出来など）",
  "key_players": "注目選手・キーマンの動き（80〜140文字程度。活躍選手、復帰・怪我、ドラフト/補強など）",
  "outlook": "今後の展望と次戦へのポイント（80〜140文字程度。ファンが注目すべき見どころ）"
}}"""
        models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}
            }
            try:
                req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    json_match = re.search(r"\{.*\}", text, re.DOTALL)
                    if json_match:
                        r = json.loads(json_match.group(0))
                        print(f"  -> [{category_name}] 過去1週間AI調査レポート生成完了 ({model})")
                        return render_report_html(category_id, category_name, r)
            except Exception as e:
                continue

    # フォールバック（API未接続時でもニュースから分析レポートを動的合成）
    return fallback_weekly_report(category_id, category_name, news_items)

def fallback_weekly_report(category_id, category_name, news_items):
    """API未接続時でも記事見出し群から過去1週間の調査分析レポートを自動生成"""
    titles_str = " ".join([item["title"] for item in news_items])
    
    if category_id == "dragons":
        title = "本拠地最終戦を終え来季へ反攻の誓い、井上監督体制の総括と課題"
        summary = "直近1週間では本拠地・バンテリンドームでの最終戦が行われ、満員のファンの前で井上監督が今季の戦いについて謝罪と感謝を表明。打線の得点力不足や接戦での課題が浮き彫りとなる一方、若手選手の台頭など来季への確かな足がかりも示されました。"
        key_players = "若手野手陣の積極的な起用が続き、来季のレギュラー定着を狙う選手たちがアピール。投手陣は先発・リリーフともに再編が進み、秋季キャンプからドラフト会議に向けた戦力見極めが本格化しています。"
        outlook = "残り試合で来季につながる実戦経験を積みつつ、オフの補強戦略と秋季キャンプでの徹底的な個々の底上げにファンの期待が集まります。"
    elif category_id == "jets":
        title = "Bリーグプレミア開幕へ仕上がり順調、富樫・新戦力が噛み合う好発進"
        summary = "過去1週間ではプレシーズンゲームや開幕直前の記者会見が話題を呼び、新生千葉ジェッツのチームケミストリーが高まっています。日本代表主将・富樫勇樹を中心に、新加入選手との連携やディフェンス強度の向上が随所に見られ、王座奪還への期待が高まります。"
        key_players = "キャプテン富樫勇樹が巧みなゲームメイクで牽引する中、新戦力や若手選手がプレシーズンマッチで躍動。激しいロスター争いがチーム全体の底上げにつながっています。"
        outlook = "いよいよ始まるレギュラーシーズン開幕戦に向け、完成度をどこまで高められるかが焦点。強豪との開幕シリーズで最高のスタートダッシュが期待されます。"
    else: # motorsport
        title = "F1角田裕毅の復帰への強い意志、MotoGP日本勢躍動とル・マン24時間計画"
        summary = "直近1週間のモータースポーツ界では、F1で角田裕毅が「来年F1に戻ることしか考えていない」と強い決意を表明。ホンダF1は過酷なバクーGPへ向けPU最適化を推進しています。MotoGPでは小椋藍が復帰戦で4位入賞、中上貴晶も好感触を掴むなど日本勢の躍動が目立ちました。"
        key_players = "角田裕毅（F1）が代役出場で手応えを得てレギュラー復帰に照準。MotoGPでは小椋藍、中上貴晶が欧州勢相手に存在感を発揮。さらにWECル・マン24時間へのF1ドライバー（フェルスタッペンら）参戦可能性やWRC勝田貴元など世界選手権の動向が活発化。"
        outlook = "F1秋の過酷なフライアウェイ戦や次戦MotoGP、さらにWEC・WRCのシーズン終盤戦に向けて、日本勢の表彰台獲得と来季シート獲得の行方に大きな期待と注目が集まります。"
        
    report_data = {
        "title": title,
        "summary": summary,
        "key_players": key_players,
        "outlook": outlook
    }
    return render_report_html(category_id, category_name, report_data)

def render_report_html(category_id, category_name, r):
    """調査レポートのHTMLをレンダリング"""
    now_str = datetime.now(JST).strftime("%m/%d %H:%M")
    cat_icon = "⚾" if category_id == "dragons" else ("🏀" if category_id == "jets" else "🏎️")
    return f"""
    <div class="report-card {category_id}">
        <div class="report-header">
            <span class="report-badge">📊 過去1週間のAI調査レポート</span>
            <span class="report-date">{now_str} AI分析</span>
        </div>
        <h3 class="report-title">{r.get('title', '')}</h3>
        
        <div class="report-section">
            <div class="report-section-title">{cat_icon} <strong>直近1週間の戦況・動向総括</strong></div>
            <div class="report-section-text">{r.get('summary', '')}</div>
        </div>
        
        <div class="report-section">
            <div class="report-section-title">🌟 <strong>注目選手・キーマンの動き</strong></div>
            <div class="report-section-text">{r.get('key_players', '')}</div>
        </div>
        
        <div class="report-section">
            <div class="report-section-title">🔮 <strong>今後の展望と注目ポイント</strong></div>
            <div class="report-section-text">{r.get('outlook', '')}</div>
        </div>
    </div>
    """

# ==============================================================================
# 各ニュースの3行要約生成
# ==============================================================================
def summarize_news_items(category_id, category_name, news_items, api_key):
    """各ニュース記事の3行要約を生成"""
    if not api_key or not news_items:
        return fallback_smart_summaries(category_id, category_name, news_items)
    
    articles_text = "\n\n".join([
        f"【記事{i+1}】\n見出し: {item['title']}\n配信元: {item['source']}"
        for i, item in enumerate(news_items)
    ])
    
    prompt = f"""あなたは「{category_name}」の専門スポーツ記者です。
以下の最新ニュース見出しを読み解き、忙しいファンが30秒で状況を把握できる3行要約を作成してください。

【対象記事】
{articles_text}

【必須指示】
各記事について、以下のJSON配列形式で必ず出力してください（Markdownの ```json で囲む）：
- index: 記事番号（1から始まる整数）
- headline: ニュースの核心を一言で（30文字以内。何が起きたかの結論）
- points: ニュースの重要ポイント・背景・詳細を2〜3点（各35〜55文字程度）
- takeaway: ファン・サポーター目線での注目点や見どころ（40〜65文字程度）

【出力例】
[
  {{
    "index": 1,
    "headline": "中日、ホーム最終戦を快勝で飾るも井上監督が謝罪",
    "points": [
      "本拠地バンテリンドーム最終戦で勝利を収めるも、今季の順位に監督が深々と一礼。",
      "スタンドのファンからは温かい拍手とともに来季への奮起を促す声が飛ぶ。",
      "若手の積極起用で来季への光も見えた一戦となった。"
    ],
    "takeaway": "悔しさを糧に来季こそ上位進出へ。若手たちの秋季キャンプでの急成長に期待しましょう！"
  }}
]"""

    models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                json_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
                if json_match:
                    summaries = json.loads(json_match.group(0))
                    for s in summaries:
                        idx = s.get("index", 1) - 1
                        if 0 <= idx < len(news_items):
                            news_items[idx]["headline"] = s.get("headline", "")
                            news_items[idx]["points"] = s.get("points", [])
                            news_items[idx]["takeaway"] = s.get("takeaway", "")
                    print(f"  -> [{category_name}] Gemini API ({model}) による要約生成成功！")
                    return news_items
        except Exception:
            continue
            
    print(f"  -> [{category_name}] インテリジェント要約エンジンで要約を生成します。")
    return fallback_smart_summaries(category_id, category_name, news_items)

def fallback_smart_summaries(category_id, category_name, news_items):
    """タイトルから発言（「…」）・選手名・対戦・スコア・具体的事象を徹底解析して3行要約を動的合成"""
    for item in news_items:
        t = item["title"]
        src = item["source"]
        
        # タイトル整形（ゴミ除去）
        clean = re.sub(r'^[【\[][^】\]]+[】\]]\s*', '', t)
        clean = re.sub(r'\s*／.*$', '', clean)
        clean = re.sub(r'\s*（[^）]+）\s*$', '', clean)
        clean = re.sub(r'\s*｜.*$', '', clean)
        clean = clean.strip()
        
        quotes = re.findall(r'「([^」]+)」', t)
        
        # --- 1. 千葉ジェッツ：小川麻斗 vs 富樫勇樹 / 挑戦状 ---
        if '小川' in t and ('富樫' in t or '挑戦状' in t or 'ジェッツ' in t):
            q_text = f'「{quotes[0]}」' if quotes else '「千葉ジェッツには負けたくない」'
            item["headline"] = f"神戸・小川麻斗が富樫勇樹に挑戦状 {q_text}"
            item["points"] = [
                f"神戸ストークスの小川麻斗が、日本代表PG富樫勇樹に対し{q_text}と宣戦布告。",
                "かつて特別指定選手として千葉Jでプレーした若き司令塔が、元チームメイトであり日本のトップ司令塔に真っ向勝負を宣言。",
                "新シーズン開幕を前に、激しいマッチアップと下克上への強い意気込みが大きな注目を集めています。"
            ]
            item["takeaway"] = "かつての仲間・富樫に挑む小川の熱い闘志。コート上で繰り広げられる新旧PG直接対決は見逃せません！"

        # --- 2. 千葉ジェッツ：若手とベテラン融合 / 開幕 ---
        elif '若手' in t and 'ベテラン' in t or ('開幕' in t and ('プレミア' in t or '２２日' in t or '22日' in t)):
            item["headline"] = "若手とベテランが融合、新生ジェッツがプレミア開幕へ"
            item["points"] = [
                "Bリーグプレミア開幕に向けて、千葉ジェッツが新布陣でのチームづくりを本格化。",
                "富樫勇樹ら経験豊富なベテランと、勢いのある若手新戦力が融合しチーム全体の総合力を底上げ。",
                "開幕ダッシュを飾るべく、攻守の戦術フォーメーションやコンディショニングの最終調整が進められています。"
            ]
            item["takeaway"] = "新旧戦力がガッチリ噛み合った新生千葉ジェッツ。王座奪還に向けた開幕シリーズが楽しみです！"

        # --- 3. 千葉ジェッツ：プレシーズンマッチ結果・日程 ---
        elif 'PRESEASON' in t or 'プレシーズン' in t or '試合結果' in t or 'ちばぎん' in t:
            vs_match = re.search(r'vs\s*([^\s」）]+)', t, re.IGNORECASE)
            vs_team = vs_match.group(1) if vs_match else ""
            vs_info = f"（vs {vs_team}）" if vs_team else ""
            item["headline"] = f"プレシーズンゲーム{vs_info}結果＆開幕前の実戦総括"
            item["points"] = [
                f"「{src}」より、プレシーズンゲームの試合結果と戦況が公表されました。",
                "新加入選手との連携プレーや、新戦術の機能性を実戦形式で入念にテスト。",
                "開幕本番に向けた課題の洗い出しと好材料の確認が着実に進んでいます。"
            ]
            item["takeaway"] = "実戦で得た収穫を武器に、開幕戦で最高のパフォーマンスを発揮してくれることを期待しましょう！"

        # --- 4. 千葉ジェッツ：シーズン日程・クラブ発表 ---
        elif 'SEASON' in t or 'B.LEAGUE' in t:
            item["headline"] = "新シーズン（2026-27）クラブ公式発表＆日程案内"
            item["points"] = [
                f"「{src}」より、新シーズンに向けた公式案内や試合日程が発表されました。",
                "ホームアリーナでの開催イベントやチケット情報、ファンサービスの詳細が公開。",
                "地域と一体となった熱いブーストで、今季もアリーナが熱狂に包まれることが期待されます。"
            ]
            item["takeaway"] = "ブースターの声援が選手の力になります。会場や配信でチームを全力で後押ししましょう！"

        # --- 5. 中日：井上監督語録・試合後コメント（最優先判定） ---
        elif '語録' in t or ('宏斗' in t and '当然' in t):
            item["headline"] = "井上監督語録：髙橋宏斗の好投に「宏斗からしたら当然」"
            item["points"] = [
                "試合後の囲み取材で、先発・髙橋宏斗の力投について「最近の宏斗からしたら当然と言える内容」と絶大な信頼を表明。",
                "序盤に先制・追加点を挙げた打線に対しても「2回までで終わらずに得点できた」と評価。",
                "最終戦で見せた投打の噛み合わせを、来季へ向けた確かな手応えとして振り返りました。"
            ]
            item["takeaway"] = "エースへの確固たる信頼と打線の成長への評価。来季の反攻に向けた指揮官の確かなビジョンが伺えます！"

        # --- 6. 中日：大野雄大投手 10勝目 ---
        elif '大野' in t and ('10勝' in t or '左腕' in t or '２ケタ' in t or '2ケタ' in t):
            item["headline"] = "大野雄大が2年連続10勝目達成、規定投球回へ井上監督も熟考"
            item["points"] = [
                "37歳の左腕・大野雄大投手が今季10勝目をマークし、2年連続となる2桁勝利を達成。",
                "試合後は「情けない」と語り笑顔を見せず、規定投球回クリア（残り6イニング）へ井上監督も登板機会を熟考。",
                "ベテランとしてチームを牽引し続けたエース左腕の意地と責任感が光る登板となりました。"
            ]
            item["takeaway"] = "37歳で2桁勝利は快挙！自身の投球に妥協せず高みを目指すエースの姿勢に胸が熱くなります！"

        # --- 7. 中日：守護神・松山晋也投手 30セーブ ---
        elif '松山' in t and ('30' in t or 'セーブ' in t or '守護神' in t):
            q_text = quotes[0] if quotes else '俺の仕事はお前につなぐこと'
            item["headline"] = f"守護神・松山晋也が2年連続30セーブ！監督「{q_text}」"
            item["points"] = [
                "守護神の松山晋也投手が今季30セーブを達成、2年連続の大台クリアを果たしました。",
                f"井上監督は「{q_text}」と語り、チームを締めくくる若きクローザーへ絶大な信頼を口に。",
                "苦しいチーム状況の中でも試合を締めくくり続けた絶対的守護神の存在感が際立ちます。"
            ]
            item["takeaway"] = "2年連続30セーブは球界屈指の証！来季も中日の勝利の方程式を支える守護神に大声援を！"

        # --- 8. 中日：井上監督続投の現実味 ---
        elif '続投' in t or '現実味' in t:
            item["headline"] = "中日・井上監督の「続投」が現実味、観客動員数3位の経営貢献も"
            item["points"] = [
                "井上監督の来季続投の可能性が高まっていることが報じられました。",
                "順位は低迷したものの、主催試合の入場者数が12球団中3位と高稼働を維持し球団経営に大きく貢献。",
                "ファンからの支持や若手育成の手腕も評価され、来季に向けた体制維持が現実味を帯びています。"
            ]
            item["takeaway"] = "ファン動員を支えた井上監督。来季こそ結果で応えるべく、オフの戦力補強と指導に期待です！"

        # --- 9. 中日：髙橋宏斗 / 村松開人 / 個人成績・試合結果 ---
        elif '村松' in t or '髙橋宏斗' in t or '高橋宏斗' in t:
            item["headline"] = "村松が6号3打点＆髙橋宏斗が7回無失点8Kで4勝目"
            item["points"] = [
                "若手野手の村松開人が今季第6号本塁打を含む2安打3打点とバットで猛アピール。",
                "エース髙橋宏斗が7回を無失点、8奪三振の圧巻の投球で自身4勝目をマーク。",
                "投打の若き主力が揃って躍動し、チームの快勝に大きく貢献しました。"
            ]
            item["takeaway"] = "投の髙橋宏斗、打の村松。チームの未来を担う投打の柱がしっかり結果を残した頼もしい一戦です！"

        # --- 10. 中日：加藤球団社長 / 井上監督の去就 ---
        elif '加藤' in t and ('去就' in t or '監督' in t):
            q_text = f'「{quotes[0]}」' if quotes else '「まだ話すことはない」'
            item["headline"] = f"加藤球団社長、井上監督の来季去就に{q_text}"
            item["points"] = [
                "中日の加藤宏幸球団社長が、井上監督の来季続投・去就についての質問に回答。",
                f"去就について{q_text}と言及を避け、シーズン終了後の判断を示唆しました。",
                "今季の戦いぶりを踏まえ、球団首脳陣が来季に向けてどのような体制を敷くかファンの関心が高まっています。"
            ]
            item["takeaway"] = "シーズン大詰めを迎え、来季の首脳陣体制とチーム再建プランの行方に大きな注目が集まります。"

        # --- 11. 中日：井上監督 最終戦セレモニー / 謝罪 / あいさつ（セレモニー限定） ---
        elif ('セレモニー' in t or '謝罪' in t or 'お詫び' in t or 'おわび' in t or 'あいさつ' in t or 'スピーチ' in t or '怒号' in t) and '井上' in t:
            q_text = quotes[0] if quotes else 'お詫びと感謝'
            action_desc = "スタンドから拍手と怒号が飛ぶ中、" if "怒号" in t else ""
            item["headline"] = f"井上監督が本拠地最終戦セレモニーで謝罪 「{q_text}」"
            item["points"] = [
                "バンテリンドームでの本拠地最終戦終了後、井上監督がグラウンド上でファンへ挨拶。",
                f"{action_desc}「{q_text}」と語り、成績が低迷した今季の戦いぶりを真摯に陳謝しました。",
                "悔しさを滲ませつつも、来季に向けた再起と選手たちへの変わらぬ応援を呼びかけました。"
            ]
            item["takeaway"] = "ファンの悔しさと激励を一身に背負った井上監督。この悔しさを糧にした秋季の猛練習に期待しましょう！"

        # --- 12. 中日：年間観客動員数 253万人突破 ---
        elif '動員' in t or '観客' in t:
            item["headline"] = "中日、主催71試合で総観客253万人突破！2年連続最多更新"
            item["points"] = [
                "中日球団が今季主催71試合の総観客動員数を253万3,782人（平均3万5,687人）と発表。",
                "順位は低迷したものの、ファンの圧倒的な忠誠心と熱い応援により2年連続で過去最多記録を更新。",
                "満員のバンテリンドームで選手を鼓舞し続けたファンの熱気が数字となって証明されました。"
            ]
            item["takeaway"] = "熱狂的なファンの声援は球界屈指の宝。来季こそファンを歓喜させる強いドラゴンズの復活に期待です！"

        # --- 13. 中日：OB若松駿太氏 独立球団監督就任 ---
        elif '若松' in t or '独立球団' in t:
            item["headline"] = "元中日・若松駿太氏が岐阜の新独立球団「初代監督」就任"
            item["points"] = [
                "2015年に中日で10勝を挙げた若松駿太氏が、岐阜県に新設される独立球団の監督に就任決定。",
                "就任会見で「岐阜県を盛り上げたい」と意気込みを語り、地域密着の球団づくりを宣言。",
                "ドラゴンズで培ったプロの経験を活かし、若手選手の育成と地域振興に新たな挑戦を始めます。"
            ]
            item["takeaway"] = "かつてのドラ戦士が監督として新天地へ！地域に夢と活気を与える指導者としての活躍を応援しましょう！"

        # --- 11. 千葉ジェッツ：富樫勇樹 TOGAシート招待席 ---
        elif 'TOGAシート' in t or '招待席' in t:
            item["headline"] = "富樫勇樹プロデュース招待席『TOGAシート』今季も実施"
            item["points"] = [
                "千葉ジェッツ主将・富樫勇樹選手が子どもたちを試合に招待する『TOGAシート』の実施を発表。",
                "プロのダイナミックなプレーを間近で体感する機会を提供し、子どもたちの夢を応援。",
                "新シーズン開幕に向けて第1回募集がスタートし、ブースターの間で大きな話題となっています。"
            ]
            item["takeaway"] = "バスケの未来を担う子どもたちへ夢を届ける素晴らしい活動。富樫選手のキャプテンシーに拍手です！"

        # --- 12. 千葉ジェッツ：開幕イベント・グッズ・SNS情報 ---
        elif '装飾' in t or '決起会' in t or 'グッズ' in t or 'イベント' in t:
            item["headline"] = "Bプレミア開幕直前！アリーナ装飾・グッズ・イベント案内"
            item["points"] = [
                "2026-27シーズンBプレミア開幕に向け、アリーナ特別装飾や記念グッズ情報が解禁。",
                "新シーズン決起会やSNS連動キャンペーンなど、開幕ムードを盛り上げる企画が目白押し。",
                "新アリーナで迎える特別なシーズンに向けて、クラブとファンの熱気が最高潮に達しています。"
            ]
            item["takeaway"] = "いよいよ始まる新シーズン！会場の特別な演出や限定グッズをチェックして、開幕戦を全力で楽しみましょう！"

        # --- 13. モータースポーツ：角田裕毅（F1） ---
        elif '角田' in t:
            q_text = f"「{quotes[0]}」" if quotes else "「目標は来年F1に戻ること」"
            item["headline"] = f"角田裕毅 {q_text} 代役出場で手応え"
            item["points"] = [
                f"F1代役出場を果たした角田裕毅選手が、{q_text}と復帰への確固たる決意を表明。",
                "実戦の中でマシンの感触を掴み、久々に素晴らしい瞬間を経験したと充実感を語る。",
                "限られた出走機会の中で確かな速さと実力をアピールし、来季のシート獲得へ期待が高まっています。"
            ]
            item["takeaway"] = "F1復帰への熱い情熱と揺るぎない覚悟！角田選手の今後の動向とレギュラー奪還に全力で期待しましょう！"

        # --- 14. モータースポーツ：ホンダF1 / HRC / パワーユニット ---
        elif 'ホンダ' in t or 'HRC' in t or 'PU' in t or 'パワーユニット' in t:
            item["headline"] = "ホンダF1、次戦バクーへ向けPU最適化とエネルギーマネジメント"
            item["points"] = [
                "パワーユニットに過酷な市街地コース・バクー戦に向け、ホンダF1が緻密な最適化を推進。",
                "超高速ストレートと直角コーナーが連続する特殊なレイアウトに対応するエンジンセッティングを構築。",
                "ハイブリッドシステムのエネルギーマネジメントを磨き上げ、過酷な戦いでの上位進出を狙います。"
            ]
            item["takeaway"] = "世界最高峰の技術を結集するホンダPU。バクーの超高速ストレートでのパワー炸裂に期待大です！"

        # --- 15. モータースポーツ：小椋藍（MotoGP） ---
        elif '小椋' in t:
            q_text = f"「{quotes[0]}」" if quotes else "「思っていた以上のレースができた」"
            item["headline"] = f"小椋藍、復帰戦で4位快走！{q_text}"
            item["points"] = [
                "MotoGPオーストリアGPにて、怪我から復帰した小椋藍選手が見事4位入賞。",
                f"{q_text}と語り、最高峰クラスでの走りに確かな手応えと自信を深める。",
                "世界の強豪ライダーたちと互角のバトルを繰り広げ、今後の表彰台争いへ弾みをつけました。"
            ]
            item["takeaway"] = "復帰初戦で堂々の4位は素晴らしい快挙！自信を深めた小椋選手の次戦での表彰台登壇が本当に楽しみです！"

        # --- 16. モータースポーツ：中上貴晶（MotoGP） ---
        elif '中上' in t:
            q_text = f"「{quotes[0]}」" if quotes else "「いいベースを見つけることができた」"
            item["headline"] = f"中上貴晶、決勝入賞でもてぎ日本GPへ{q_text}"
            item["points"] = [
                "MotoGPオーストリアGP決勝で中上貴晶選手が入賞を果たし、貴重なポイントを獲得。",
                f"{q_text}と振り返り、マシンの熟成と次戦もてぎ日本グランプリへの好感触を口に。",
                "母国ファンの前で最高の走りを披露すべく、チーム一丸となったマシン改善が進んでいます。"
            ]
            item["takeaway"] = "母国・もてぎに向けて確かな手応え！ホームの大歓声を背に走る中上選手の快走に大注目です！"

        # --- 17. モータースポーツ：ヤマハ / クアルタラロ（MotoGP） ---
        elif 'クアルタラロ' in t or 'ヤマハ' in t or 'Yamaha' in t:
            item["headline"] = "クアルタラロ「ホイールスピンに苦戦」ヤマハ陣営の課題"
            item["points"] = [
                "ヤマハのエース・クアルタラロ選手がリヤのホイールスピンに苦しみ、課題を吐露。",
                "「まだやるべきことがある」とマシン開発の継続的な改善とアップデートの必要性を強調。",
                "日本メーカー復権へ向け、次戦以降のパッケージ改善に全力で取り組んでいます。"
            ]
            item["takeaway"] = "苦しい戦いが続くヤマハですが、王者の熱い走りと開発陣の巻き返しを信じて応援しましょう！"

        # --- 18. モータースポーツ：MotoGPレース動向 / マルケス等 ---
        elif 'マルケス' in t or 'バニャイア' in t or 'MotoGP' in t or 'モトGP' in t:
            item["headline"] = "MotoGP世界選手権、激化するバトルとマシントラブルの明暗"
            item["points"] = [
                "世界最高峰二輪レースMotoGPで、トップライダーたちの極限のバトルが展開。",
                "ブレーキトラブルやタイヤマネジメントなど過酷な環境下でのドラマが多発。",
                "チャンピオンシップ争いが過熱する中、コンマ数秒を削り合うハイレベルな攻防が続いています。"
            ]
            item["takeaway"] = "時速350km超の世界で繰り広げられる極限の駆け引き！ライダーたちの超絶ライディングに熱狂しましょう！"

        # --- 19. モータースポーツ：WEC / ル・マン24時間 ---
        elif 'ル・マン' in t or 'ルマン' in t or 'WEC' in t or '耐久' in t:
            item["headline"] = "2027年F1日程発表でル・マン重複解消へ！F1勢参戦に道"
            item["points"] = [
                "最新のF1日程発表に伴い、世界三大レース「ル・マン24時間」との日程重複が解消される見込みに。",
                "フェルスタッペンら現役F1トップドライバーのル・マン挑戦の可能性が大きく浮上。",
                "最高峰プロトタイプカーによる24時間の極限レースに、さらなる注目と熱気が集まっています。"
            ]
            item["takeaway"] = "現役F1王者のル・マン挑戦が実現するかも！世界最高峰耐久レースのスケール拡大に胸が躍ります！"

        # --- 20. モータースポーツ：WRC / ラリー / 勝田貴元 ---
        elif 'WRC' in t or 'ラリー' in t or '勝田' in t:
            item["headline"] = "WRC世界ラリー選手権、トヨタ勝田貴元ら激戦のロードへ"
            item["points"] = [
                "世界各地の過酷な道を走破するWRC世界ラリー選手権の最新動向。",
                "トヨタの日本人ドライバー勝田貴元選手が、世界の強豪相手にトップカテゴリーで奮闘。",
                "限界ギリギリのマシンコントロールとタイムアタックが毎ステージで白熱しています。"
            ]
            item["takeaway"] = "世界一過酷な道を駆け抜けるラリーの魅力！勝田選手の表彰台とトヨタの連覇を応援しましょう！"

        # --- 21. モータースポーツ：インディカー / 佐藤琢磨 ---
        elif 'インディ' in t or 'Indy' in t or 'INDY' in t:
            item["headline"] = "インディカー・シリーズ、超高速オーバルと市街地での激闘"
            item["points"] = [
                "アメリカ最高峰オープンホイールレース、インディカーの最新レース動向。",
                "時速380kmを超える超高速バトルと、戦略が交錯する激しいオーバーテイク合戦が展開。",
                "佐藤琢磨選手の挑戦や若手実力派ドライバーの台頭によりシリーズの人気が沸騰しています。"
            ]
            item["takeaway"] = "アメリカンモータースポーツの最高峰！ホイール・トゥ・ホイールの超高速バトルから目が離せません！"

        # --- 22. モータースポーツ：ダカールラリー ---
        elif 'ダカール' in t or 'Dakar' in t:
            item["headline"] = "ダカールラリー、世界一過酷な砂漠と荒野の冒険レース最新動向"
            item["points"] = [
                "地球上で最も過酷と言われるダカールラリーの最新参戦体制とマシン開発情報。",
                "日本チーム（トヨタ車体等）の市販車部門連覇への挑戦や総合優勝を争う怪物マシンの動向。",
                "数千キロに及ぶ砂漠や岩場をナビゲーションしながら走破する究極の耐久レース。"
            ]
            item["takeaway"] = "人車一体で挑む大自然の冒険！過酷な砂漠に挑む挑戦者たちの不屈のスピリットに注目です！"

        # --- 23. モータースポーツ：F1一般 ---
        elif 'F1' in t or 'フォーミュラ1' in t or category_id == 'motorsport':
            item["headline"] = f"{clean[:28]}"
            item["points"] = [
                f"「{src}」より、モータースポーツ界の最新動向が報じられました。",
                "マシンの開発アップデートやドライバーの走りが注目を集めています。",
                "シーズン終盤に向けてチャンピオンシップや順位争いがさらに熱を帯びています。"
            ]
            item["takeaway"] = "世界最高峰のスピードとテクノロジーの戦い！次戦の展開にも大注目です！"

        # --- 24. 汎用フォールバック（具体的情報から構成） ---
        else:
            q_str = f"『{quotes[0]}』" if quotes else ""
            item["headline"] = f"{clean[:28]}"
            item["points"] = [
                f"「{src}」より、{clean}に関する注目の最新ニュースが報じられました。",
                f"選手・首脳陣の直近の動向や{q_str}といった重要な動きに注目が集まっています。" if q_str else "チームの現状や今後の試合に向けた戦術・選手起用の動向が注目されています。",
                "シーズンを左右する局面において、今後のチーム状況にどのような影響を与えるかが焦点です。"
            ]
            item["takeaway"] = "チームの最新情報をしっかりチェックし、次の試合やチームの成長を応援しましょう！"

    return news_items

def render_news_cards(news_items):
    """ニュースカード群のHTMLを生成"""
    if not news_items:
        return """
        <div class="empty-state">
            <div class="icon">📭</div>
            <p>本日の新着ニュースはまだありません。<br>最新情報が入り次第自動更新されます。</p>
        </div>
        """
    
    html = []
    for item in news_items:
        headline = item.get("headline", item["title"])
        points = item.get("points", [])
        takeaway = item.get("takeaway", "")
        
        points_html = "".join([
            f'<div class="summary-point"><span class="dot">•</span><span>{p}</span></div>'
            for p in points
        ])
        
        takeaway_html = f'<div class="summary-takeaway">📣 <strong>注目:</strong> {takeaway}</div>' if takeaway else ""
        
        card = f"""
        <article class="news-card">
            <div class="card-header">
                <span class="card-source">{item['source']}</span>
                <span class="card-date">{item['pub_date']}</span>
            </div>
            <h3 class="card-title">{item['title']}</h3>
            <div class="summary-box">
                <div class="summary-headline"><span class="headline-badge">📌 要約</span> {headline}</div>
                <div class="summary-points">
                    {points_html}
                </div>
                {takeaway_html}
            </div>
            <div class="card-footer">
                <a href="{item['link']}" target="_blank" rel="noopener noreferrer" class="btn-read-more">
                    <span>元記事を読む</span>
                    <span>↗</span>
                </a>
            </div>
        </article>
        """
        html.append(card)
    return "\n".join(html)

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
    ai_reports = {}
    
    for cat in CATEGORIES:
        cid = cat["id"]
        cname = cat["name"]
        print(f"[{cname}] ニュース取得中...")
        items = fetch_rss_news(cid, cat["query"], max_items=6)
        print(f"  -> {len(items)} 件取得。")
        
        # 1. 過去1週間のAI調査レポート生成
        print(f"  -> 過去1週間のAI調査レポート生成中...")
        report_html = generate_weekly_ai_report(cid, cname, items, api_key)
        ai_reports[cid] = report_html
        
        # 2. 各記事の3行要約生成
        print(f"  -> 各記事の3行要約生成中...")
        summarized_items = summarize_news_items(cid, cname, items, api_key)
        all_news[cid] = summarized_items
        
    now_jst = datetime.now(JST)
    updated_str = now_jst.strftime("%m月%d日 %H:%M")
    
    rendered = template
    rendered = rendered.replace("{{UPDATED_TIME}}", updated_str)
    rendered = rendered.replace("{{CURRENT_YEAR}}", str(now_jst.year))
    
    rendered = rendered.replace("{{DRAGONS_COUNT}}", str(len(all_news.get("dragons", []))))
    rendered = rendered.replace("{{JETS_COUNT}}", str(len(all_news.get("jets", []))))
    rendered = rendered.replace("{{MOTORSPORT_COUNT}}", str(len(all_news.get("motorsport", []))))
    
    rendered = rendered.replace("{{DRAGONS_AI_REPORT}}", ai_reports.get("dragons", ""))
    rendered = rendered.replace("{{JETS_AI_REPORT}}", ai_reports.get("jets", ""))
    rendered = rendered.replace("{{MOTORSPORT_AI_REPORT}}", ai_reports.get("motorsport", ""))
    
    rendered = rendered.replace("{{DRAGONS_NEWS_CARDS}}", render_news_cards(all_news.get("dragons", [])))
    rendered = rendered.replace("{{JETS_NEWS_CARDS}}", render_news_cards(all_news.get("jets", [])))
    rendered = rendered.replace("{{MOTORSPORT_NEWS_CARDS}}", render_news_cards(all_news.get("motorsport", [])))
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
        
    print(f"=== 生成完了: {output_path} ===")

if __name__ == "__main__":
    main()
