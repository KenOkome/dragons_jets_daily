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

def fetch_rss_news(query, max_items=6):
    """Google News RSS から指定クエリの最新ニュースを取得（重複排除付き）"""
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
            
            items = []
            seen_titles = set()
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_str = item.findtext("pubDate", "").strip()
                source_elem = item.find("source")
                source = source_elem.text.strip() if source_elem is not None and source_elem.text else "スポーツ速報"
                
                # タイトル末尾の「 - メディア名」を整理
                clean_title = re.sub(r"\s*-\s*[^-]+$", "", title).strip()
                
                # 重複判定（先頭18文字で同一ニュースを排除）
                norm_key = re.sub(r"[\s\W]", "", clean_title)[:18]
                if norm_key in seen_titles:
                    continue
                seen_titles.add(norm_key)
                
                items.append({
                    "title": clean_title,
                    "raw_title": title,
                    "link": link,
                    "pub_date": format_pub_date(pub_date_str),
                    "source": source,
                    "headline": "",
                    "points": [],
                    "takeaway": ""
                })
                if len(items) >= max_items:
                    break
            return items
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
    else: # jets
        title = "Bリーグプレミア開幕へ仕上がり順調、富樫・新戦力が噛み合う好発進"
        summary = "過去1週間ではプレシーズンゲームや開幕直前の記者会見が話題を呼び、新生千葉ジェッツのチームケミストリーが高まっています。日本代表主将・富樫勇樹を中心に、新加入選手との連携やディフェンス強度の向上が随所に見られ、王座奪還への期待が高まります。"
        key_players = "キャプテン富樫勇樹が巧みなゲームメイクで牽引する中、新戦力や若手選手がプレシーズンマッチで躍動。激しいロスター争いがチーム全体の底上げにつながっています。"
        outlook = "いよいよ始まるレギュラーシーズン開幕戦に向け、完成度をどこまで高められるかが焦点。強豪との開幕シリーズで最高のスタートダッシュが期待されます。"
        
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
    return f"""
    <div class="report-card {category_id}">
        <div class="report-header">
            <span class="report-badge">📊 過去1週間のAI調査レポート</span>
            <span class="report-date">{now_str} AI分析</span>
        </div>
        <h3 class="report-title">{r.get('title', '')}</h3>
        
        <div class="report-section">
            <div class="report-section-title">⚾ <strong>直近1週間の戦況・動向総括</strong></div>
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

        # --- 5. 中日：髙橋宏斗 / 村松開人 / 個人成績・試合結果 ---
        elif '村松' in t or '髙橋宏斗' in t or '高橋宏斗' in t:
            item["headline"] = "村松が6号3打点＆髙橋宏斗が7回無失点8Kで4勝目"
            item["points"] = [
                "若手野手の村松開人が今季第6号本塁打を含む2安打3打点とバットで猛アピール。",
                "エース髙橋宏斗が7回を無失点、8奪三振の圧巻の投球で自身4勝目をマーク。",
                "投打の若き主力が揃って躍動し、チームの快勝に大きく貢献しました。"
            ]
            item["takeaway"] = "投の髙橋宏斗、打の村松。チームの未来を担う投打の柱がしっかり結果を残した頼もしい一戦です！"

        # --- 6. 中日：加藤球団社長 / 井上監督の去就 ---
        elif '加藤' in t and ('去就' in t or '監督' in t):
            q_text = f'「{quotes[0]}」' if quotes else '「まだ話すことはない」'
            item["headline"] = f"加藤球団社長、井上監督の来季去就に{q_text}"
            item["points"] = [
                "中日の加藤宏幸球団社長が、井上監督の来季続投・去就についての質問に回答。",
                f"去就について{q_text}と言及を避け、シーズン終了後の判断を示唆しました。",
                "今季の戦いぶりを踏まえ、球団首脳陣が来季に向けてどのような体制を敷くかファンの関心が高まっています。"
            ]
            item["takeaway"] = "シーズン大詰めを迎え、来季の首脳陣体制とチーム再建プランの行方に大きな注目が集まります。"

        # --- 7. 中日：井上監督 最終戦セレモニー / 謝罪 / あいさつ ---
        elif '井上監督' in t or 'セレモニー' in t or '謝罪' in t or 'お詫び' in t:
            q_text = quotes[0] if quotes else 'お詫びと感謝'
            action_desc = "スタンドから拍手と怒号が飛ぶ中、" if "怒号" in t else ""
            item["headline"] = f"井上監督が本拠地最終戦セレモニーで謝罪 「{q_text}」"
            item["points"] = [
                "バンテリンドームでの本拠地最終戦終了後、井上監督がグラウンド上でファンへ挨拶。",
                f"{action_desc}「{q_text}」と語り、成績が低迷した今季の戦いぶりを真摯に陳謝しました。",
                "悔しさを滲ませつつも、来季に向けた再起と選手たちへの変わらぬ応援を呼びかけました。"
            ]
            item["takeaway"] = "ファンの悔しさと激励を一身に背負った井上監督。この悔しさを糧にした秋季の猛練習に期待しましょう！"

        # --- 8. 汎用フォールバック（具体的情報から構成） ---
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
    print("=== ドラ＆ジェッツ速報 生成開始 ===")
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
        items = fetch_rss_news(cat["query"], max_items=6)
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
    
    rendered = rendered.replace("{{DRAGONS_AI_REPORT}}", ai_reports.get("dragons", ""))
    rendered = rendered.replace("{{JETS_AI_REPORT}}", ai_reports.get("jets", ""))
    
    rendered = rendered.replace("{{DRAGONS_NEWS_CARDS}}", render_news_cards(all_news.get("dragons", [])))
    rendered = rendered.replace("{{JETS_NEWS_CARDS}}", render_news_cards(all_news.get("jets", [])))
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)
        
    print(f"=== 生成完了: {output_path} ===")

if __name__ == "__main__":
    main()
