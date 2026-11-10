#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
まいすぽ 自動生成スクリプト (generate_news.py)
- 第1タブ（ドラゴンズ＆NPB）: 中日ドラゴンズ 4枠 ＋ NPB全体トレンド 2枠
- 第2タブ（ジェッツ＆Bリーグ）: 千葉ジェッツ 4枠 ＋ Bリーグ全体トレンド 2枠
- 第3タブ（モータースポーツ）: F1 / MotoGP / WRC / WEC / Indy 等から多ジャンル 6枠
- 第4タブ（世界のメジャースポーツ）: 王道グローバル（最大2枠）＋ 世界開拓競技（3枠）＋ 特定地域の熱狂ユニーク競技（毎日1枠確定）の完全異種6競技
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
from concurrent.futures import ThreadPoolExecutor

# 日本時間 (JST)
JST = timezone(timedelta(hours=9))

CATEGORIES = [
    {
        "id": "dragons",
        "name": "中日ドラゴンズ＆NPB",
        "icon": "🐉",
        "desc": "中日ドラゴンズ最新4枠 ＋ NPB他球団・リーグ全体トレンド2枠"
    },
    {
        "id": "jets",
        "name": "千葉ジェッツ＆Bリーグ",
        "icon": "✈️",
        "desc": "千葉ジェッツ最新4枠 ＋ Bリーグ全体・代表トレンド2枠"
    },
    {
        "id": "motorsport",
        "name": "モータースポーツ",
        "icon": "🏎️",
        "desc": "F1、MotoGPを中心にWRC、WEC、Indy等の日本勢＆世界トップレース要約"
    },
    {
        "id": "world",
        "name": "世界のメジャースポーツ＆地域熱狂競技",
        "icon": "🌍",
        "desc": "世界6大異種競技を厳選！毎日1枠「特定地域で熱狂されるユニーク競技」を解説付きで紹介"
    }
]

# 世界スポーツ：Pool A（王道グローバル：合計最大2枠まで）
WORLD_MAINSTREAM_POOLS = [
    {
        "genre_id": "soccer_europe",
        "sub_tag": "⚽ 欧州サッカー",
        "query_ja": "(チャンピオンズリーグ OR プレミアリーグ OR ラ・リーガ OR セリエA OR ブンデスリーガ OR レアル・マドリード OR バルセロナ OR リバプール OR マンチェスター OR アーセナル OR 三笘薫 OR 久保建英) (試合 OR 結果 OR ゴール OR 勝利 OR 決勝 OR 首位) when:7d",
        "query_en": None
    },
    {
        "genre_id": "mlb_baseball",
        "sub_tag": "⚾ MLB・米野球",
        "query_ja": "(MLB OR メジャーリーグ OR ワールドシリーズ OR ドジャース OR ヤンキース OR 大谷翔平 OR 山本由伸 OR 今永昇太) (試合 OR 結果 OR 受賞 OR MVP OR FA OR 移籍 OR 契約 OR 本塁打) -中日スポーツ when:7d",
        "query_en": None
    },
    {
        "genre_id": "nba_basketball",
        "sub_tag": "🏀 NBA・米バスケ",
        "query_ja": "(NBA OR レイカーズ OR セルティックス OR ウォリアーズ OR 八村塁 OR 河村勇輝) (試合 OR 勝利 OR 得点 OR 結果 OR 開幕 OR プレーオフ) when:7d",
        "query_en": None
    }
]

# 世界スポーツ：Pool B（世界開拓メジャースポーツ：3〜4枠選出、各ジャンル最大1枠）
WORLD_FRONTIER_POOLS = [
    {
        "genre_id": "nfl_football",
        "sub_tag": "🏈 NFL・米アメフト",
        "query_ja": "(NFL OR スーパーボウル OR マホームズ OR チーフス) (タッチダウン OR 勝利 OR 逆転 OR 連勝) -告発 -逮捕 -Xリーグ when:7d",
        "query_en": "(\"NFL\") (touchdown OR win OR overtime OR Mahomes) -arrest -lawsuit when:3d"
    },
    {
        "genre_id": "nhl_hockey",
        "sub_tag": "🏒 NHL・氷上ホッケー",
        "query_ja": "(NHL OR スタンレーカップ) (アイスホッケー OR 勝利 OR ゴール OR 連勝) when:7d",
        "query_en": "(\"NHL\") (hockey OR win OR goal OR overtime) when:3d"
    },
    {
        "genre_id": "tennis_golf",
        "sub_tag": "🎾⛳ 世界テニス・ゴルフ",
        "query_ja": "(ATPツアー OR WTA OR PGAツアー OR LPGA OR 松山英樹 OR シナー OR アルカラス) (テニス OR ゴルフ) (優勝 OR 決勝 OR 勝利 OR 首位) when:7d",
        "query_en": "(\"ATP Tour\" OR \"PGA Tour\" OR \"LPGA\") (win OR final OR title OR champion) when:3d"
    },
    {
        "genre_id": "rugby_volley",
        "sub_tag": "🏉🏐 ラグビー・バレー",
        "query_ja": "(ラグビー日本代表 OR オールブラックス OR リーグワン OR バレーボール OR SVリーグ OR 石川祐希) (試合 OR 勝利 OR 決勝 OR 逆転 OR 連勝) -高校 -中学 -ビジュアル -血管 when:7d",
        "query_en": None
    },
    {
        "genre_id": "combat_sports",
        "sub_tag": "🥊🥋 UFC・世界格闘技",
        "query_ja": "(UFC OR ボクシング世界戦 OR 井上尚弥 OR 中谷潤人 OR 柔道グランドスラム) (勝利 OR KO OR 判定 OR 防衛 OR 王者 OR 優勝) when:7d",
        "query_en": None
    },
    {
        "genre_id": "winter_olympic",
        "sub_tag": "⛸️🚴 氷雪・自転車・卓球",
        "query_ja": "(フィギュアスケート OR GPシリーズ OR スキージャンプ OR カーリング OR ツール・ド・フランス OR WTT卓球) (優勝 OR 表彰台 OR 決勝 OR 首位) when:7d",
        "query_en": None
    }
]

# 世界スポーツ：Pool C（特定地域で熱狂的人気のユニーク競技：毎日必ず1枠確定、日替わりローテーション優先）
# ※日本語の3文字略称（AFL=アフラック株、IPL=脱毛、PBR=株価倍率等）による異業種ニュース誤爆を防ぐため、現地英語ニュースまたは厳密な日本語競技名から取得
REGIONAL_UNIQUE_POOLS = [
    {
        "genre_id": "unique_cricket",
        "sub_tag": "🌏 地域熱狂：クリケット(印・英豪)",
        "region_hint": "インド・英連邦・豪州で10億人以上が熱狂する世界競技人口第2位の国民的バット＆ボール競技",
        "query_ja": "(\"クリケット\" AND (インド OR イングランド OR オーストラリア OR 代表 OR 試合 OR 選手権)) -株 -投資 when:7d",
        "query_en": "(\"Test cricket\" OR \"ICC\" OR \"Indian cricket\" OR \"Ashes\" OR \"T20\") (match OR win OR century OR wicket OR series) when:3d"
    },
    {
        "genre_id": "unique_kabaddi",
        "sub_tag": "🌏 地域熱狂：カバディ(インド国技)",
        "region_hint": "インドのプロリーグ(PKL)で数億人が熱狂する、無呼吸で敵陣へ乗り込む『鬼ごっこ×格闘技』",
        "query_ja": "(\"カバディ\" AND (インド OR 代表 OR 試合 OR 選手権 OR リーグ)) when:7d",
        "query_en": "(\"Pro Kabaddi\" OR \"Kabaddi\") (match OR win OR raid OR points OR league) when:7d"
    },
    {
        "genre_id": "unique_afl",
        "sub_tag": "🌏 地域熱狂：オージーボール(豪州)",
        "region_hint": "オーストラリアで観客動員数No.1を誇る、巨大な楕円形フィールドで空中戦とタックルを繰り広げる豪州国技(AFL)",
        "query_ja": "(\"オージーボール\" OR \"オーストラリアンフットボール\") when:7d",
        "query_en": "(\"Australian rules football\" OR \"AFLW\" OR \"AFL Premiership\") (match OR win OR goal OR final) when:4d"
    },
    {
        "genre_id": "unique_snooker",
        "sub_tag": "🌏 地域熱狂：スヌーカー(英・中国)",
        "region_hint": "イギリスや中国で絶大なテレビ視聴率を誇る、通常の約2倍巨大な台でミリ単位の精密ショットを競う頭脳ビリヤード",
        "query_ja": "(\"スヌーカー\" AND (優勝 OR 決勝 OR 選手権 OR オサリバン OR トランプ)) when:7d",
        "query_en": "(\"World Snooker\" OR \"Snooker Championship\" OR \"Ronnie O'Sullivan\" OR \"Judd Trump\") (win OR final OR tournament OR century) when:4d"
    },
    {
        "genre_id": "unique_darts",
        "sub_tag": "🌏 地域熱狂：PDCダーツ(英国・欧州)",
        "region_hint": "イギリス・オランダ・ドイツで数千人の観客が仮装して大合唱する、賞金数億円規模の熱狂的アリーナスポーツ",
        "query_ja": "(\"PDC\" AND \"ダーツ\") when:7d",
        "query_en": "(\"PDC Darts\" OR \"Grand Slam of Darts\" OR \"Luke Littler\" OR \"Luke Humphries\") (darts OR win OR final OR 180) when:4d"
    },
    {
        "genre_id": "unique_padel",
        "sub_tag": "🌏 地域熱狂：パデル(スペイン・南米)",
        "region_hint": "スペインやアルゼンチンでテニスを超える競技人口を持ち、強化ガラスの壁バウンドを使って戦う高速ダブルス競技",
        "query_ja": "(\"パデル\" AND (大会 OR ツアー OR 選手権 OR 代表 OR 優勝)) when:7d",
        "query_en": "(\"Premier Padel\" OR \"Padel Tour\") (win OR final OR title OR champion) when:7d"
    },
    {
        "genre_id": "unique_gaa",
        "sub_tag": "🌏 地域熱狂：ハーリング＆ゲーリック(愛)",
        "region_hint": "アイルランドで8万人満員のスタジアムを揺らす、時速150kmで球が飛び交う地上最速の古代スティック球技＆国技",
        "query_ja": "(\"ゲーリックフットボール\") when:7d",
        "query_en": "(\"GAA\" AND (\"Hurling\" OR \"Gaelic football\")) (championship OR final OR win OR club) when:4d"
    },
    {
        "genre_id": "unique_sepaktakraw",
        "sub_tag": "🌏 地域熱狂：セパタクロー(東南アジア)",
        "region_hint": "タイ・マレーシアなど東南アジアで国民的人気を誇る、手を使わず空中アクロバット回転蹴りで打ち合う『足のバレーボール』",
        "query_ja": "(\"セパタクロー\" AND (代表 OR 選手権 OR 大会 OR 試合)) when:7d",
        "query_en": "(\"Sepak Takraw\" OR \"ISTAF\") (win OR gold OR final OR tournament) when:7d"
    },
    {
        "genre_id": "unique_biathlon",
        "sub_tag": "🌏 地域熱狂：バイアスロン(北欧・独)",
        "region_hint": "ドイツやノルウェーで冬季テレビ視聴率No.1を誇る、心拍数180超のクロスカントリースキー直後に精密ライフル射撃を行う究極の動静競技",
        "query_ja": "(\"バイアスロン\" AND (W杯 OR 世界選手権 OR 代表 OR 優勝)) when:7d",
        "query_en": "(\"IBU Biathlon\" OR \"Biathlon World Cup\") (win OR sprint OR pursuit OR relay) when:7d"
    },
    {
        "genre_id": "unique_pickleball",
        "sub_tag": "🌏 地域熱狂：ピックルボール(北米)",
        "region_hint": "アメリカで競技人口が爆発的に急増しプロリーグにNBAスターらも出資する、穴あきボールとパドルで打ち合う新世代ラケット競技",
        "query_ja": "(\"ピックルボール\" AND (大会 OR 選手権 OR プロ OR ツアー)) when:7d",
        "query_en": "(\"PPA Tour\" OR \"Major League Pickleball\") (pickleball OR championship OR win OR final) when:5d"
    },
    {
        "genre_id": "unique_handball",
        "sub_tag": "🌏 地域熱狂：欧州ハンド＆フロアボール",
        "region_hint": "ドイツ・デンマーク・北欧でアリーナを満員にする空中戦ハンドボール＆北欧で絶大な人気を誇る超高速室内ホッケー",
        "query_ja": "(\"ハンドボール\" AND (欧州 OR チャンピオンズリーグ OR ドイツ OR 代表)) when:7d",
        "query_en": "(\"EHF Champions League\" OR \"IHF Handball\" OR \"World Floorball\") (win OR match OR final) when:5d"
    },
    {
        "genre_id": "unique_lacrosse_rodeo",
        "sub_tag": "🌏 地域熱狂：ラクロス＆ロデオ(北米)",
        "region_hint": "北米先住民の伝統を継ぐ時速160kmのシュートが飛び交うプロラクロス(PLL)と、荒馬・猛牛に8秒間乗り続ける米国南部の熱狂ロデオ(PBR)",
        "query_ja": "(\"ラクロス\" AND (世界選手権 OR 代表 OR 全日本)) when:7d",
        "query_en": "(\"Premier Lacrosse League\" OR \"World Lacrosse\" OR \"PBR Bull Riding\") (championship OR win OR final) when:5d"
    }
]

GEMINI_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest"
]

# 特定選手への集中を防ぐための主要選手リスト（同一人物は1日最大1記事に制限）
KNOWN_ATHLETES = [
    "久保建英", "久保", "三笘薫", "三笘", "遠藤航", "伊東純也", "鎌田大地", "堂安律", "南野拓実", "冨安健洋",
    "大谷翔平", "大谷", "山本由伸", "ダルビッシュ", "今永昇太", "鈴木誠也", "千賀滉大", "菊池雄星", "佐々木朗希",
    "八村塁", "河村勇輝", "渡邊雄太", "富樫勇樹", "原修太", "金近廉",
    "髙橋宏斗", "高橋宏斗", "大野雄大", "松山晋哉", "細川成也", "村松開人", "石川昂弥", "根尾昂", "金丸夢斗", "森駿太",
    "角田裕毅", "小椋藍", "中上貴晶", "勝田貴元", "佐藤琢磨", "フェルスタッペン", "ハミルトン", "ノリス", "マルケス",
    "井上尚弥", "中谷潤人", "那須川天心", "石川祐希", "髙橋藍", "早田ひな", "張本智和", "張本美和", "松山英樹"
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

def extract_primary_athlete(title):
    """タイトルに含まれる主要選手名を抽出（同一選手の重複排除用）"""
    for name in KNOWN_ATHLETES:
        if name in title:
            # 表記揺れ正規化
            if name in ("久保", "久保建英"):
                return "久保建英"
            if name in ("三笘", "三笘薫"):
                return "三笘薫"
            if name in ("大谷", "大谷翔平"):
                return "大谷翔平"
            if name in ("髙橋宏斗", "高橋宏斗"):
                return "髙橋宏斗"
            return name
    return None

def is_duplicate_topic(title, selected_titles, threshold=0.32):
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
    """鮮度（公開からの経過時間）＋ 見出しの具体性をスコアリング（※特定個人名への偏重ボーナスは廃止）"""
    score = 0.0
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

    if "「" in title and "」" in title:
        score += 3.0
    if re.search(r"\d+", title):
        score += 2.0
    if any(w in title for w in [
        "勝利", "快勝", "逆転", "本塁打", "ホームラン", "ゴール", "優勝", "表彰台",
        "決定", "就任", "ドラフト", "契約", "開幕", "連勝", "新記録", "王座", "制覇",
        "win", "final", "champion", "title", "victory", "record"
    ]):
        score += 2.5
    return score

def fetch_rss_raw(query, lang="ja", max_age_hours=240.0):
    """Google News RSS から候補記事リストを取得（日本語・英語両対応）"""
    if not query:
        return []
    encoded_query = urllib.parse.quote(query)
    if lang == "en":
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    else:
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
    )
    now_jst = datetime.now(JST)
    candidates = []
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            xml_data = resp.read()
            root = ET.fromstring(xml_data)
            for item in root.findall(".//item"):
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub_date_str = item.findtext("pubDate", "").strip()
                desc_raw = item.findtext("description", "").strip()
                source_elem = item.find("source")
                source = source_elem.text.strip() if source_elem is not None and source_elem.text else ("Global Sports" if lang == "en" else "スポーツ速報")

                clean_title = re.sub(r"\s*[-|]\s*[^-|]+$", "", title).strip()
                snippet = strip_html_tags(desc_raw)
                if snippet.startswith(clean_title):
                    snippet = snippet[len(clean_title):].strip(" -|　")

                # 金融・株式・美容・ゴシップ記事の混入を完全遮断
                noise_words = ["株価", "目標株価", "ファイナンス", "Investing", "FX", "株式市場", "光脱毛", "医療脱毛", "週刊女性"]
                if any(nw in (clean_title + " " + source) for nw in noise_words):
                    continue

                pub_dt = parse_pub_datetime(pub_date_str)
                if pub_dt is not None:
                    age_hours = max(0.0, (now_jst - pub_dt).total_seconds() / 3600.0)
                    if age_hours > max_age_hours:
                        continue
                    pub_date_display = pub_dt.strftime("%m/%d %H:%M")
                    is_new = (age_hours <= 28.0)
                else:
                    age_hours = 48.0
                    pub_date_display = "最新速報"
                    is_new = False

                candidates.append({
                    "title": clean_title,
                    "raw_title": title,
                    "snippet": snippet[:240],
                    "link": link,
                    "pub_date": pub_date_display,
                    "age_hours": age_hours,
                    "is_new": is_new,
                    "source": source,
                    "lang": lang,
                    "score": score_article(clean_title, age_hours),
                    "sub_tag": "",
                    "sub_type": "normal",
                    "region_hint": "",
                    "headline": "",
                    "points": [],
                    "takeaway": ""
                })
    except Exception as e:
        print(f"  [RSS取得警告] ({query[:30]}...): {e}", file=sys.stderr)
    return candidates

def select_unique_items(candidates, count, selected_titles, athlete_counts, max_per_athlete=1, sub_tag="", sub_type="normal", region_hint=""):
    """重複・同一選手集中を排除しながら指定件数を厳選"""
    candidates.sort(key=lambda x: x["score"], reverse=True)
    picked = []
    for cand in candidates:
        if is_duplicate_topic(cand["title"], selected_titles):
            continue
        athlete = extract_primary_athlete(cand["title"])
        if athlete and athlete_counts.get(athlete, 0) >= max_per_athlete:
            continue
        if athlete:
            athlete_counts[athlete] = athlete_counts.get(athlete, 0) + 1
        selected_titles.append(cand["title"])
        cand["sub_tag"] = sub_tag or cand.get("sub_tag", "")
        cand["sub_type"] = sub_type
        if region_hint:
            cand["region_hint"] = region_hint
        picked.append(cand)
        if len(picked) >= count:
            break
    return picked

def fetch_dragons_and_npb():
    """第1タブ: 中日ドラゴンズ 4枠 ＋ NPB全体トレンド（他球団・侍J・FA等）2枠"""
    q_dragons = "(\"中日ドラゴンズ\" OR \"ドラゴンズ\") (試合 OR 勝 OR 敗 OR 選手 OR 監督 OR 工藤 OR 井上 OR ドラフト OR 契約更改 OR キャンプ OR 補強 OR 移籍 OR 現役ドラフト OR FA OR 戦力外 OR 自主トレ OR オープン戦 OR 成績) when:7d"
    q_npb = "(\"プロ野球\" OR NPB OR セ・リーグ OR パ・リーグ OR 侍ジャパン OR プレミア12 OR 日本シリーズ OR FA宣言 OR 契約更改 OR ドラフト OR 沢村賞 OR ゴールデングラブ) -中日 -ドラゴンズ when:7d"

    dragons_keywords = [
        "中日", "ドラゴンズ", "工藤", "井上", "立浪", "バンテリン", "ナゴヤ",
        "髙橋宏斗", "高橋宏斗", "大野", "松山", "細川", "村松", "石川昂",
        "根尾", "金丸", "森駿太", "清水", "柳", "福永", "岡林", "涌井", "宏斗", "竜"
    ]
    raw_d = [
        c for c in fetch_rss_raw(q_dragons, "ja")
        if any(k in c["title"] for k in dragons_keywords)
        and not ("順位表" in c["title"] and not c["title"].startswith(("【中日", "中日", "ドラゴンズ")))
    ]
    raw_npb = [
        c for c in fetch_rss_raw(q_npb, "ja")
        if not any(k in c["title"] for k in ["中日", "ドラゴンズ"])
        and any(k in (c["title"] + " " + c["snippet"]) for k in ["プロ野球", "NPB", "侍ジャパン", "巨人", "阪神", "広島", "DeNA", "ヤクルト", "ソフトバンク", "日本ハム", "ロッテ", "楽天", "オリックス", "西武", "FA", "契約更改", "プレミア12", "日本シリーズ"])
    ]

    selected_titles = []
    athlete_counts = {}
    items_d = select_unique_items(raw_d, 4, selected_titles, athlete_counts, max_per_athlete=1, sub_tag="🐉 中日ドラゴンズ", sub_type="team")
    items_npb = select_unique_items(raw_npb, 2, selected_titles, athlete_counts, max_per_athlete=1, sub_tag="⚾ NPB全体トレンド", sub_type="league")

    items_d.sort(key=lambda x: x["age_hours"])
    items_npb.sort(key=lambda x: x["age_hours"])
    return items_d + items_npb

def fetch_jets_and_bleague():
    """第2タブ: 千葉ジェッツ 4枠 ＋ Bリーグ全体トレンド（他クラブ・Bプレミア・代表等）2枠"""
    q_jets = "(\"千葉ジェッツ\" OR \"千葉ジェッツふなばし\" OR \"富樫勇樹\" OR \"渡邊雄太\" OR \"原修太\") (試合 OR 勝利 OR 敗戦 OR Bリーグ OR Bプレミア OR 節 OR 天皇杯 OR CS OR チャンピオンシップ OR 開幕 OR 移籍 OR バスケ) when:7d"
    q_bleague = "(\"Bリーグ\" OR \"B.LEAGUE\" OR \"B1\" OR \"Bプレミア\" OR \"バスケ日本代表\" OR \"アカツキジャパン\" OR \"アルバルク東京\" OR \"宇都宮ブレックス\" OR \"琉球ゴールデンキングス\" OR \"川崎ブレイブサンダース\" OR \"サンロッカーズ渋谷\" OR \"名古屋ダイヤモンドドルフィンズ\") -千葉ジェッツ -富樫 -渡邊雄太 when:7d"

    jets_keywords = [
        "ジェッツ", "千葉J", "富樫", "渡邊雄太", "原修太", "金近", "小川",
        "ホグ", "ムーニー", "船橋", "LaLa arena", "ららアリーナ", "Bリーグ", "B.LEAGUE", "Bプレミア"
    ]
    raw_j = [
        c for c in fetch_rss_raw(q_jets, "ja")
        if any(k in (c["title"] + " " + c["snippet"]) for k in jets_keywords)
    ]
    raw_b = [
        c for c in fetch_rss_raw(q_bleague, "ja")
        if not any(k in c["title"] for k in ["千葉ジェッツ", "千葉J", "富樫", "渡邊雄太"])
    ]

    selected_titles = []
    athlete_counts = {}
    items_j = select_unique_items(raw_j, 4, selected_titles, athlete_counts, max_per_athlete=1, sub_tag="✈️ 千葉ジェッツ", sub_type="team")
    items_b = select_unique_items(raw_b, 2, selected_titles, athlete_counts, max_per_athlete=1, sub_tag="🏀 Bリーグ全体トレンド", sub_type="league")

    items_j.sort(key=lambda x: x["age_hours"])
    items_b.sort(key=lambda x: x["age_hours"])
    return items_j + items_b

def detect_motorsport_tag(title):
    """モータースポーツ記事のカテゴリーバッジ判定"""
    t = title
    if any(k in t for k in ["MotoGP", "小椋", "中上", "マルケス", "バニャイア", "ヤマハ", "ホンダHRC"]):
        return "🏍️ MotoGP"
    if any(k in t for k in ["WRC", "ラリー", "勝田"]):
        return "🚗 WRC・ラリー"
    if any(k in t for k in ["WEC", "ル・マン", "耐久"]):
        return "🏁 WEC・耐久"
    if any(k in t for k in ["インディ", "Indy", "佐藤琢磨", "スーパーフォーミュラ", "SUPER GT", "スーパーGT"]):
        return "🏎️ Indy・国内トップ"
    return "🏎️ F1"

def fetch_motorsport_diverse():
    """第3タブ: モータースポーツ（F1・MotoGP・WRC・WEC・Indy等をバランスよく6枠）"""
    q_ms = "(F1 OR MotoGP OR 角田裕毅 OR 小椋藍 OR ホンダF1 OR WRC OR WEC OR インディカー) (GP OR 決勝 OR 予選 OR 表彰台 OR 参戦 OR 結果 OR レース) when:7d"
    raw = fetch_rss_raw(q_ms, "ja")
    selected_titles = []
    athlete_counts = {}
    items = select_unique_items(raw, 6, selected_titles, athlete_counts, max_per_athlete=1, sub_type="normal")
    for it in items:
        it["sub_tag"] = detect_motorsport_tag(it["title"])
    items.sort(key=lambda x: x["age_hours"])
    return items

def fetch_pool_top_candidate(pool, selected_titles, athlete_counts):
    """指定された競技プールから最もスコアの高い1件を取得（日本語優先・英語フォールバック）"""
    cands = fetch_rss_raw(pool["query_ja"], "ja")
    picked = select_unique_items(
        cands, 1, selected_titles, athlete_counts,
        max_per_athlete=1,
        sub_tag=pool["sub_tag"],
        sub_type="unique" if pool["genre_id"].startswith("unique_") else "frontier" if pool in WORLD_FRONTIER_POOLS else "normal",
        region_hint=pool.get("region_hint", "")
    )
    if picked:
        return picked[0]
    if pool.get("query_en"):
        cands_en = fetch_rss_raw(pool["query_en"], "en")
        picked_en = select_unique_items(
            cands_en, 1, selected_titles, athlete_counts,
            max_per_athlete=1,
            sub_tag=pool["sub_tag"],
            sub_type="unique" if pool["genre_id"].startswith("unique_") else "frontier",
            region_hint=pool.get("region_hint", "")
        )
        if picked_en:
            return picked_en[0]
    return None

def fetch_world_diverse():
    """
    第4タブ: 世界のメジャースポーツ＆地域熱狂ユニーク競技（全6枠すべて異種競技）
    - 1枠確定: Pool C（特定地域で熱狂的人気のユニーク競技：日替わりローテーション優先）
    - 最大2枠: Pool A（王道グローバル：欧州サッカー / MLB / NBA から各最大1枠・計最大2枠）
    - 3〜4枠: Pool B（世界開拓メジャースポーツ：NFL / NHL / テニス・ゴルフ / ラグビー・バレー / UFC・格闘技 / ウィンター・自転車・卓球）
    """
    selected_titles = []
    athlete_counts = {}

    # 1. 特定地域の熱狂ユニーク競技（毎日1枠確定・日替わりで開始インデックスをローテーション）
    day_idx = datetime.now(JST).timetuple().tm_yday
    num_unique = len(REGIONAL_UNIQUE_POOLS)
    rotated_unique_pools = [REGIONAL_UNIQUE_POOLS[(day_idx + i) % num_unique] for i in range(num_unique)]

    unique_slot_item = None
    for upool in rotated_unique_pools:
        cand = fetch_pool_top_candidate(upool, selected_titles, athlete_counts)
        if cand:
            unique_slot_item = cand
            break

    # 2. Pool A（王道グローバル）と Pool B（世界開拓スポーツ）を並列取得
    all_ab_pools = WORLD_MAINSTREAM_POOLS + WORLD_FRONTIER_POOLS
    pool_results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        future_map = {ex.submit(fetch_rss_raw, p["query_ja"], "ja"): p for p in all_ab_pools}
        for fut, p in future_map.items():
            try:
                pool_results[p["genre_id"]] = fut.result()
            except Exception:
                pool_results[p["genre_id"]] = []

    # Pool A（欧州サッカー・MLB・NBA）からは上位最大2ジャンル（各1件）まで
    mainstream_candidates = []
    for p in WORLD_MAINSTREAM_POOLS:
        raw_list = pool_results.get(p["genre_id"], [])
        picked = select_unique_items(raw_list, 1, selected_titles, athlete_counts, max_per_athlete=1, sub_tag=p["sub_tag"], sub_type="normal")
        if picked:
            mainstream_candidates.append(picked[0])
    mainstream_candidates.sort(key=lambda x: x["score"], reverse=True)
    chosen_mainstream = mainstream_candidates[:2]

    # Pool B（NFL・NHL・テニス/ゴルフ・ラグビー/バレー・UFC/格闘技・ウィンター/自転車/卓球）から残り枠（3〜4枠）をすべて異なるジャンルで選出
    needed_frontier = 6 - (1 if unique_slot_item else 0) - len(chosen_mainstream)
    frontier_candidates = []
    for p in WORLD_FRONTIER_POOLS:
        raw_list = pool_results.get(p["genre_id"], [])
        picked = select_unique_items(raw_list, 1, selected_titles, athlete_counts, max_per_athlete=1, sub_tag=p["sub_tag"], sub_type="frontier")
        if not picked and p.get("query_en"):
            raw_en = fetch_rss_raw(p["query_en"], "en")
            picked = select_unique_items(raw_en, 1, selected_titles, athlete_counts, max_per_athlete=1, sub_tag=p["sub_tag"], sub_type="frontier")
        if picked:
            frontier_candidates.append(picked[0])

    # 日によって選ばれる開拓スポーツも偏らないようスコア＋日替わり微調整で上位を選出
    frontier_candidates.sort(key=lambda x: x["score"], reverse=True)
    chosen_frontier = frontier_candidates[:needed_frontier]

    # 並び順：①地域熱狂ユニーク競技（最上段に特別枠として配置）→ ②世界開拓スポーツ → ③王道グローバル
    final_items = []
    if unique_slot_item:
        final_items.append(unique_slot_item)
    final_items.extend(chosen_frontier)
    final_items.extend(chosen_mainstream)
    return final_items[:6]

def fetch_category_news(category_id):
    """カテゴリーIDに応じたニュース取得ディスパッチャ"""
    if category_id == "dragons":
        return fetch_dragons_and_npb()
    elif category_id == "jets":
        return fetch_jets_and_bleague()
    elif category_id == "motorsport":
        return fetch_motorsport_diverse()
    else:
        return fetch_world_diverse()

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
    """過去7日分のアーカイブJSONから主要ニュース見出しを取得し、1週間レポートの文脈を補強（特定選手への偏り防止付き）"""
    archive_dir = os.path.join(script_dir, "docs", "data", "archive")
    if not os.path.exists(archive_dir):
        return []
    files = sorted([f for f in os.listdir(archive_dir) if f.endswith(".json")], reverse=True)[:days]
    past_lines = []
    seen = set()
    past_athletes = {}
    for fname in files:
        fpath = os.path.join(archive_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            cat_data = data.get("categories", {}).get(category_id, {})
            for n in cat_data.get("news", [])[:3]:
                ttl = n.get("title", "").strip()
                if not ttl or ttl in seen:
                    continue
                if category_id == "world":
                    ath = extract_primary_athlete(ttl)
                    if ath and past_athletes.get(ath, 0) >= 1:
                        continue
                    if ath:
                        past_athletes[ath] = past_athletes.get(ath, 0) + 1
                seen.add(ttl)
                past_lines.append(f"- [{data.get('date', '')[5:]}] {ttl}")
        except Exception:
            continue
    return past_lines[:10]

def call_gemini_json(prompt, api_key, timeout=35):
    """Gemini API を呼び出して JSON をパースして返す"""
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
        f"- [{item.get('sub_tag', '')} | {item['pub_date']}] {item['title']} ({item['source']})"
        + (f" / 概要: {item['snippet']}" if item.get("snippet") else "")
        for item in news_items
    ])
    past_lines = load_recent_archive_headlines(script_dir, category_id, days=7)
    past_context = "\n".join(past_lines) if past_lines else "（直近取得記事を参照）"
    
    if category_id == "dragons":
        role_note = "中日ドラゴンズの動向を中心にしつつ、NPB全体（セ・パ他球団や侍ジャパン、ストーブリーグ等）の大きな動きもあわせて総括してください。"
    elif category_id == "jets":
        role_note = "千葉ジェッツの動向を中心にしつつ、Bリーグ全体（B1上位争いやBプレミア、日本代表等）のトレンドもあわせて総括してください。"
    elif category_id == "world":
        role_note = "特定選手1人に偏らず、今週の世界の多様な競技（北米4大スポーツ、欧州球技、格闘技、ウィンター競技、さらに特定地域で熱狂されるユニーク競技）のハイライトを幅広く総括してください。"
    else:
        role_note = "F1・MotoGP・WRC・WEC・Indy等の主要トピックをバランスよく総括してください。"

    if api_key:
        prompt = f"""あなたは「{category_name}」を専門に取材・分析しているスポーツアナリストです。
本日の最新ニュースおよび直近1週間のアーカイブ見出しをもとに、ファンが今一番知りたい【過去1週間の徹底調査レポート】を作成してください。
{role_note}

【本日の最新ニュース】
{current_articles_text}

【直近1週間の主な出来事（時系列アーカイブ）】
{past_context}

【厳守ルール】
1. 与えられた記事見出し・概要に含まれる事実のみに基づいて日本語で分析し、記事にないスコアや順位、発言を勝手に創作（ハルシネーション）しないでください。
2. 以下のJSONオブジェクト形式のみで出力してください：
{{
  "title": "1週間の総括見出し（35文字以内。最新の重要トピックを端的に）",
  "summary": "直近1週間の戦況・チームおよびリーグ全体の動向総括（90〜150文字程度）",
  "key_players": "注目選手・キーマン・各競技の主役たちの動き（80〜140文字程度）",
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
        "key_players": "主力選手や首脳陣の最新コメント、リーグ全体の編成・次戦に向けた調整状況に高い関心が集まっています。",
        "outlook": "今後の試合日程や各大会の展開に向け、各メディアの続報と選手のパフォーマンスに注目です。"
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
# 各ニュースの3行要約生成（英語記事の日本語翻訳＆未知の競技解説対応）
# ==============================================================================
def summarize_news_items(category_id, category_name, news_items, api_key):
    """各ニュース記事の3行要約を生成"""
    if not news_items:
        return []
    
    news_items = fallback_smart_summaries(category_id, category_name, news_items)
    if not api_key:
        return news_items
    
    articles_text = "\n\n".join([
        f"【記事{i+1}】\nジャンル: {item.get('sub_tag', category_name)}"
        + (f"\n競技背景ヒント: {item['region_hint']}" if item.get("region_hint") else "")
        + f"\n言語: {item.get('lang', 'ja')}\n公開日時: {item['pub_date']}\n見出し: {item['title']}\n配信元: {item['source']}"
        + (f"\n抜粋: {item['snippet']}" if item.get("snippet") else "")
        for i, item in enumerate(news_items)
    ])
    
    total_count = len(news_items)
    prompt = f"""あなたは「{category_name}」および世界中のあらゆるスポーツに精通したプロのスポーツ解説者です。
以下の最新ニュース全{total_count}件を分析し、ファンが30秒で核心を把握でき、かつ「普段馴染みのないスポーツでもその面白さ・凄さが直感的にわかる」日本語の3行要約を作成してください。

【対象記事】
{articles_text}

【最重要ルール（厳守）】
1. **対象記事全{total_count}件（index: 1 〜 {total_count}）すべてについて、1件も漏らさず日本語で出力してください**。
2. **英語記事の自然な日本語化**: 言語が `en`（英語）の記事については、`ja_title` に自然で魅力的な日本語見出し（40文字以内）を作成してください（日本語記事の場合は元の見出しのままで構いません）。
3. **事実厳守（ハルシネーション禁止）**: 見出しと抜粋に書かれている事実のみを基に要約し、書かれていないスコアや発言を勝手に創作しないでください。
4. **知らないスポーツ・地域熱狂競技の解説**: 「🌏 地域熱狂」や普段日本で馴染みの薄い競技（クリケット、カバディ、オージーボール、スヌーカー、PDCダーツ、パデル、ハーリング、セパタクロー、バイアスロン、NFL、NHL等）の記事では、`points` の3点目または `takeaway` に**「どこの地域でどれほど熱狂されている競技か・どんなルールや凄さがあるのか」の豆知識解説**を必ず盛り込んでください。
5. headline: 記事の結論・核心を30文字以内で端的に記述してください。
6. points: 具体的な事実・背景・競技の魅力を3点（各35〜70文字程度）で整理してください。
7. takeaway: ファン目線での見どころや、その競技ならではの注目ポイントを40〜70文字程度で記述してください（※先頭に「注目:」や「💡」は付けないでください）。

【出力JSON配列フォーマット】
[
  {{
    "index": 1,
    "ja_title": "日本語の見出し（英語記事の場合は自然な日本語へ翻訳、日本語記事はそのまま）",
    "headline": "何が起きたかの結論（30文字以内）",
    "points": [
      "具体的な事実・試合や出来事の核心（35〜70文字）",
      "その背景や大会・リーグにおける重要度（35〜70文字）",
      "今後の展開への影響、またはその競技ならではのルール・熱狂度の豆知識（35〜70文字）"
    ],
    "takeaway": "ファン目線での具体的な見どころ・そのスポーツの面白さ（40〜70文字）"
  }}
]"""

    parsed, used_model = call_gemini_json(prompt, api_key)
    if isinstance(parsed, list):
        for s in parsed:
            if not isinstance(s, dict):
                continue
            idx = s.get("index", 1) - 1
            if 0 <= idx < len(news_items):
                if news_items[idx].get("lang") == "en" and s.get("ja_title"):
                    news_items[idx]["title"] = str(s.get("ja_title", "")).strip()
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
    """API障害時でも安全に要約を構成（地域熱狂競技の解説ヒント対応）"""
    for item in news_items:
        t = item["title"]
        src = item["source"]
        snippet = item.get("snippet", "")
        region_hint = item.get("region_hint", "")
        
        clean = re.sub(r"^[【\[][^】\]]+[】\]]\s*", "", t)
        clean = re.sub(r"\s*[／｜|].*$", "", clean).strip()
        quotes = re.findall(r"「([^」]+)」", t)
        
        item["headline"] = clean[:30] if len(clean) > 30 else clean
        pts = [f"「{src}」より、{clean}に関する最新動向が報じられました。"]
        if quotes:
            pts.append(f"記事内では「{quotes[0]}」といった注目の発言・コメントが伝えられています。")
        elif snippet and snippet != clean:
            pts.append(f"詳細抜粋：{snippet[:65]}...")
        else:
            pts.append(f"{item.get('sub_tag', category_name)}の最新戦況に関わる注目トピックです。")
        if region_hint:
            pts.append(f"【競技解説】{region_hint}。")
        else:
            pts.append("最新の動向や続報はリンク先の元記事全文から確認できます。")
        
        item["points"] = pts
        item["takeaway"] = region_hint if region_hint else f"{item.get('sub_tag', category_name)}の最新動向をチェックして次戦や今後の展開に注目しましょう！"
    return news_items

def render_news_cards(news_items):
    """ニュースカード群のHTMLを生成（ジャンルバッジ・NEWバッジ・XSSエスケープ対応）"""
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
        sub_tag = str(item.get("sub_tag", "")).strip()
        sub_type = str(item.get("sub_type", "normal")).strip()
        
        points = item.get("points", [])
        points_html = "".join([
            f'<div class="summary-point"><span class="dot">•</span><span>{html.escape(str(p), quote=True)}</span></div>'
            for p in points
        ])
        
        takeaway_clean = clean_takeaway_text(item.get("takeaway", ""))
        takeaway_esc = html.escape(takeaway_clean, quote=True)
        takeaway_html = f'<div class="summary-takeaway">📣 <strong>注目:</strong> {takeaway_esc}</div>' if takeaway_esc else ""
        
        new_badge_html = '<span class="badge-new">NEW</span>' if is_new else ""
        sub_tag_html = f'<span class="badge-subtag subtag-{html.escape(sub_type, quote=True)}">{html.escape(sub_tag, quote=True)}</span>' if sub_tag else ""
        card_classes = ["news-card"]
        if is_new:
            card_classes.append("is-new")
        if sub_type in ("league", "unique", "frontier"):
            card_classes.append(f"card-type-{sub_type}")
        
        card = f"""
        <article class="{' '.join(card_classes)}" data-url="{link_esc}">
            <div class="card-header">
                <div class="card-meta-left">
                    {new_badge_html}
                    {sub_tag_html}
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
                "sub_tag": n.get("sub_tag", ""),
                "sub_type": n.get("sub_type", "normal"),
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
        items = fetch_category_news(cid)
        print(f"  -> {len(items)} 件取得。")
        total_fetched += len(items)
        
        print(f"  -> 過去1週間のAI調査レポート生成中...")
        report_html, report_obj = generate_weekly_ai_report(cid, cname, items, api_key, script_dir)
        ai_reports_html[cid] = report_html
        ai_report_objs[cid] = report_obj
        time.sleep(1)
        
        print(f"  -> 各記事の3行要約生成中...")
        summarized_items = summarize_news_items(cid, cname, items, api_key)
        all_news[cid] = summarized_items
        time.sleep(1)
        
    if total_fetched == 0:
        print("エラー: 全カテゴリのニュース取得件数が0件のため更新を中断します。", file=sys.stderr)
        sys.exit(1)
        
    now_jst = datetime.now(JST)
    updated_str = now_jst.strftime("%m月%d日 %H:%M")
    
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
