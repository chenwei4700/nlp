# -*- coding: utf-8 -*-
"""
NLP 期末專案 -- 同學 A：資料工程師
Yahoo 奇摩運動 中職(CPBL) / 美職(MLB) 新聞爬蟲

使用 Yahoo Sports Sitemap 取得文章 URL，
再逐篇爬取標題、日期、內文，最後輸出乾淨 CSV。
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import json
import os
from datetime import datetime
from urllib.parse import unquote
from xml.etree import ElementTree as ET

# ============================================================
# 設定
# ============================================================
BASE_URL = "https://tw.sports.yahoo.com"
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap-index.xml"

# 每個類別要抓的目標篇數
TARGET_PER_LABEL = 500

# 請求間隔（秒），避免被封鎖
MIN_DELAY = 1.0
MAX_DELAY = 2.5

# 輸出路徑
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "baseball_news.csv")

# HTTP Headers
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# URL 解碼後的關鍵字，用來判斷類別
CPBL_KEYWORDS = [
    "中職", "中華職棒", "cpbl",
    "中信兄弟", "兄弟象", "統一獅", "統一7",
    "樂天桃猿", "桃猿", "lamigo",
    "富邦悍將", "悍將", "味全龍", "台鋼雄鷹", "雄鷹",
    "獅隊", "猿隊", "龍隊",
]

MLB_KEYWORDS = [
    "mlb", "milb", "大聯盟", "美職",
    "洋基", "道奇", "大都會", "紅襪", "太空人", "天使",
    "教士", "勇士", "費城人", "響尾蛇", "金鶯", "光芒",
    "藍鳥", "小熊", "紅人", "守護者", "老虎", "雙城",
    "皇家", "水手", "運動家", "海盜", "紅雀", "釀酒人",
    "巨人", "馬林魚", "國民", "遊騎兵", "落磯", "白襪",
    "大谷翔平", "大谷", "ohtani",
    "佐佐木朗希", "佐佐木",
    "林維恩", "林昱珉", "張育成",  # 旅外選手 -> MLB context
]

# XML namespace
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ============================================================
# Phase 1：從 Sitemap 蒐集文章 URL
# ============================================================
def fetch_sitemap_index():
    """取得 sitemap index，回傳每日 sitemap URL 列表"""
    print("[Phase 1] Reading Sitemap Index...")
    resp = requests.get(SITEMAP_INDEX_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    sitemap_urls = []
    for sitemap in root.findall("sm:sitemap", NS):
        loc = sitemap.find("sm:loc", NS)
        if loc is not None:
            sitemap_urls.append(loc.text.strip())
    print(f"  Found {len(sitemap_urls)} daily sitemaps")
    return sitemap_urls


def fetch_daily_sitemap(sitemap_url):
    """解析一個每日 sitemap，回傳所有文章 URL"""
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        urls = []
        for url_elem in root.findall("sm:url", NS):
            loc = url_elem.find("sm:loc", NS)
            if loc is not None:
                urls.append(loc.text.strip())
        return urls
    except Exception as e:
        print(f"  [WARN] Cannot read {sitemap_url}: {type(e).__name__}")
        return []


def classify_url(url):
    """根據 URL 解碼後的 slug 判斷類別"""
    # 解碼 URL 中的中文字元
    decoded_url = unquote(url).lower()

    # 排除影片 URL
    if "/video/" in decoded_url:
        return None

    # 只處理 /news/ 路徑
    if "/news/" not in decoded_url:
        return None

    # 提取 slug 部分（/news/ 之後的內容）
    slug_match = re.search(r"/news/(.+?)(?:-\d+)?\.html", decoded_url)
    if not slug_match:
        return None
    slug = slug_match.group(1)

    # 檢查是否匹配 CPBL 或 MLB 關鍵字
    is_cpbl = any(kw in slug for kw in CPBL_KEYWORDS)
    is_mlb = any(kw in slug for kw in MLB_KEYWORDS)

    # 如果同時匹配兩邊，看哪邊更多
    if is_cpbl and is_mlb:
        cpbl_count = sum(1 for kw in CPBL_KEYWORDS if kw in slug)
        mlb_count = sum(1 for kw in MLB_KEYWORDS if kw in slug)
        return "CPBL" if cpbl_count >= mlb_count else "MLB"

    if is_cpbl:
        return "CPBL"
    if is_mlb:
        return "MLB"

    return None


def collect_article_urls():
    """從所有 sitemap 蒐集 CPBL 和 MLB 文章 URL"""
    sitemap_urls = fetch_sitemap_index()

    cpbl_urls = []
    mlb_urls = []

    for i, sitemap_url in enumerate(sitemap_urls):
        # 從 URL 提取日期用於顯示
        date_match = re.search(r"sitemap-(\d{4}-\d{2}-\d{2})", sitemap_url)
        date_str = date_match.group(1) if date_match else "unknown"
        print(f"  [{i+1}/{len(sitemap_urls)}] Parsing {date_str}...", end="")

        all_urls = fetch_daily_sitemap(sitemap_url)

        daily_cpbl = 0
        daily_mlb = 0

        for url in all_urls:
            label = classify_url(url)
            if label == "CPBL" and len(cpbl_urls) < TARGET_PER_LABEL:
                cpbl_urls.append(url)
                daily_cpbl += 1
            elif label == "MLB" and len(mlb_urls) < TARGET_PER_LABEL:
                mlb_urls.append(url)
                daily_mlb += 1

        print(f" CPBL +{daily_cpbl} (total:{len(cpbl_urls)})  MLB +{daily_mlb} (total:{len(mlb_urls)})")

        # 已達目標就停止
        if len(cpbl_urls) >= TARGET_PER_LABEL and len(mlb_urls) >= TARGET_PER_LABEL:
            print("  [OK] Collected enough URLs, stopping scan")
            break

        time.sleep(0.3)

    print(f"\n[Phase 1 Done] CPBL: {len(cpbl_urls)} URLs, MLB: {len(mlb_urls)} URLs")
    return cpbl_urls, mlb_urls


# ============================================================
# Phase 2：爬取文章內頁
# ============================================================
def clean_text(text):
    """清洗文字：移除多餘空白、特殊字元"""
    if not text:
        return ""
    # 移除 HTML entities
    text = re.sub(r"&\w+;", " ", text)
    # 移除連續空白/換行
    text = re.sub(r"\s+", " ", text)
    # 移除前後空白
    text = text.strip()
    return text


def extract_from_json_ld(soup):
    """嘗試從 JSON-LD 結構化資料擷取文章資訊"""
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            # 可能是陣列或物件
            if isinstance(data, list):
                for item in data:
                    if item.get("@type") in ("NewsArticle", "Article"):
                        data = item
                        break
                else:
                    continue

            if data.get("@type") in ("NewsArticle", "Article"):
                title = data.get("headline", "")
                date_str = data.get("datePublished", "")
                body = data.get("articleBody", "")
                return title, date_str, body
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return None, None, None


def extract_from_html(soup):
    """Fallback：從 HTML 元素擷取文章資訊"""
    # 標題
    title = ""
    title_elem = soup.find("h1")
    if title_elem:
        title = title_elem.get_text(strip=True)

    # 日期
    date_str = ""
    time_elem = soup.find("time")
    if time_elem:
        date_str = time_elem.get("datetime", "") or time_elem.get_text(strip=True)

    # 內文 - 嘗試多種常見的文章容器
    body = ""
    content_selectors = [
        {"class": re.compile(r"caas-body|article-body|content-body", re.I)},
        {"class": "caas-content-wrapper"},
        {"itemprop": "articleBody"},
    ]
    for selector in content_selectors:
        content_div = soup.find("div", selector)
        if content_div:
            # 移除不需要的元素
            for unwanted in content_div.find_all(
                ["script", "style", "iframe", "figure", "figcaption", "aside", "nav"]
            ):
                unwanted.decompose()
            body = content_div.get_text(separator=" ", strip=True)
            break

    return title, date_str, body


def parse_date(date_str):
    """將各種日期格式統一為 YYYY-MM-DD"""
    if not date_str:
        return ""
    # ISO 格式
    for fmt in [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    # 嘗試擷取 YYYY-MM-DD 部分
    match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
    if match:
        return match.group(1)
    return date_str


def scrape_article(url):
    """爬取單篇文章，回傳 (title, date, content) 或 None"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 優先使用 JSON-LD
        title, date_str, body = extract_from_json_ld(soup)

        # Fallback 到 HTML 解析
        if not title or not body:
            h_title, h_date, h_body = extract_from_html(soup)
            title = title or h_title
            date_str = date_str or h_date
            body = body or h_body

        title = clean_text(title)
        body = clean_text(body)
        date_str = parse_date(date_str)

        if not title or not body:
            return None

        return title, date_str, body

    except Exception as e:
        print(f"    [FAIL] {type(e).__name__} for {url[:80]}")
        return None


def scrape_all_articles(urls, label):
    """批量爬取文章"""
    results = []
    total = len(urls)
    failed = 0

    print(f"\n[Phase 2] Scraping {label} articles ({total} total)...")

    for i, url in enumerate(urls):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{total}] Progress {(i+1)/total*100:.1f}% | OK {len(results)} | Fail {failed}")

        result = scrape_article(url)
        if result:
            title, date_str, body = result
            results.append({
                "date": date_str,
                "title": title,
                "content": body,
                "label": label,
            })
        else:
            failed += 1

        # 隨機延遲
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        time.sleep(delay)

    print(f"  [DONE] {label}: OK {len(results)}/{total}, Failed {failed}")
    return results


# ============================================================
# Phase 3：存檔
# ============================================================
def save_csv(all_articles):
    """將文章存為 CSV"""
    df = pd.DataFrame(all_articles)

    # 排除空內容
    df = df[df["content"].str.len() > 50]

    # 依日期排序
    df = df.sort_values("date", ascending=True).reset_index(drop=True)

    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[Phase 3] CSV saved to: {OUTPUT_CSV}")
    print(f"  Total rows: {len(df)}")
    print(f"  CPBL: {len(df[df['label'] == 'CPBL'])} articles")
    print(f"  MLB:  {len(df[df['label'] == 'MLB'])} articles")
    print(f"  Date range: {df['date'].min()} ~ {df['date'].max()}")

    # 顯示前 5 筆
    print("\n  Preview (first 5 rows):")
    for _, row in df.head(5).iterrows():
        print(f"    [{row['label']}] {row['date']} | {row['title'][:40]}...")

    return df


# ============================================================
# 主程式
# ============================================================
def main():
    print("=" * 60)
    print("  NLP Final Project -- Yahoo Sports News Scraper")
    print(f"  Target: CPBL {TARGET_PER_LABEL} + MLB {TARGET_PER_LABEL}")
    print("=" * 60)

    start_time = time.time()

    # Phase 1: 蒐集 URL
    cpbl_urls, mlb_urls = collect_article_urls()

    if not cpbl_urls and not mlb_urls:
        print("[ERROR] No article URLs found. Check network connection.")
        return

    # Phase 2: 爬取文章
    cpbl_articles = scrape_all_articles(cpbl_urls, "CPBL")
    mlb_articles = scrape_all_articles(mlb_urls, "MLB")

    all_articles = cpbl_articles + mlb_articles

    if not all_articles:
        print("[ERROR] No articles scraped successfully.")
        return

    # Phase 3: 存檔
    df = save_csv(all_articles)

    elapsed = time.time() - start_time
    print(f"\n[ALL DONE] Total time: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
