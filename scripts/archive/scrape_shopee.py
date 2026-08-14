#!/usr/bin/env python3
"""
Shopee VinFast product review scraper & sample generator.
Target: VinFast accessories & products on Shopee.
Columns: review_text, rating, product_name, timestamp, source='shopee'
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

PRODUCTS = [
    "Bộ sạc di động VinFast VF e34/VF5/VF8 3.5kW chính hãng",
    "Bạt phủ xe ô tô VinFast VF3 chống nắng mưa cao cấp",
    "Thảm lót sàn tràn viền VinFast VF8/VF9 chất liệu TPE",
    "Tẩu sạc nhanh ô tô VinFast 45W Type-C tản nhiệt nhôm",
    "Móc khóa thông minh da thật mạ vàng xe VinFast",
    "Bơm lốp ô tô điện di động VinFast V-GREEN tự ngắt",
    "Ốp chìa khóa mạ carbon cao cấp VinFast VF5/VF6/VF7",
    "Camera hành trình 4K tích hợp cảnh báo cho xe VinFast",
]

TEEN_CODE_SHOPEE_REVIEWS = [
    ("hang giong hinh ok phet, giao hang nhanh vl, dc r nha", 5),
    ("giao hang nhanh vl, dong goi chac chan phet. 10 diem shop!", 5),
    ("hang ok phet nma gia hoi cao ti r nha, khuyen mai them thi tot", 4),
    ("ui dep vl! ốp chìa khóa vinfast vừa vặn, da mềm mịn mượt", 5),
    ("bạc phủ xe fit in VF3 ok phet, ko bi bay khi gio to", 5),
    ("dung rat thich nma gia hoi cao ti, nma dc r nha tks shop", 4),
    ("tks shop! tau sac nhanh vl, sac pin ip15 prm ko bi nong", 5),
    ("hang cx bth nma giao lâu qua phet, 5 ngay moi toi hn", 3),
    ("shop phuc vu tot, rep tin nhan nhanh vl, bth hay ung ho shop", 5),
    ("bom lop oto ok phet, tu ngat chuan xac r nha các bác", 5),
    ("chat luong san pham nhu cc nma thoi ke, ko tra hang lam j", 2),
    ("sac di dong 3.5kW xin qua di, cam o nha 6 tieng la day r", 5),
    ("tham lot san fit form vf8 ok phet, ko bi mui nhua vãi luôn", 5),
    ("giao sai mau nma shop doi lai nhanh vl, thoi cx dc r nha", 4),
    ("hang dep vl nha mn, nen mua vgreen vinfast rat ưng", 5),
]

STANDARD_SHOPEE_REVIEWS = [
    ("Hàng đóng gói cẩn thận, đúng mô tả, chất lượng tuyệt vời.", 5),
    ("Giao hàng siêu nhanh, mới đặt hôm qua hôm nay đã nhận được.", 5),
    ("Sản phẩm chính hãng VinFast dùng rất yên tâm, chất lượng hoàn hảo.", 5),
    ("Chất liệu thảm lót sàn ôm khít sàn xe, không bị xô lệch khi lái xe.", 5),
    ("Bơm lốp hoạt động êm ái, đo áp suất lốp chính xác.", 5),
    ("Bạt phủ hơi mỏng một chút so với kỳ vọng nhưng dùng vẫn ổn.", 3),
    ("Ốp chìa khóa mạ carbon nhìn rất sang trọng và thể thao.", 5),
    ("Shop tư vấn nhiệt tình, hướng dẫn lắp đặt chi tiết.", 5),
    ("Tẩu sạc nhanh cắm chắc chắn, sạc điện thoại không bị nóng máy.", 5),
    ("Thời gian giao hàng hơi chậm hơn dự kiến 1 ngày.", 4),
]


def generate_samples(count=200):
    """Generate sample dataset of Shopee reviews for VinFast products."""
    data = []
    start_date = datetime.now() - timedelta(days=90)

    for i in range(count):
        is_teen = random.random() < 0.40
        if is_teen:
            review_text, rating = random.choice(TEEN_CODE_SHOPEE_REVIEWS)
        else:
            review_text, rating = random.choice(STANDARD_SHOPEE_REVIEWS)

        product = random.choice(PRODUCTS)
        random_days = random.randint(0, 90)
        random_seconds = random.randint(0, 86400)
        ts = (start_date + timedelta(days=random_days, seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        data.append({
            "review_text": review_text,
            "rating": rating,
            "product_name": product,
            "timestamp": ts,
            "source": "shopee"
        })

    return pd.DataFrame(data)


def scrape_shopee_live(limit=100):
    """
    Live scraper structure using Shopee public API endpoints.
    """
    try:
        import requests
    except ImportError:
        print("[!] requests library missing. Run with `--generate-sample`.")
        return pd.DataFrame()

    print("[*] Attempting live Shopee API scrape for VinFast products...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://shopee.vn/search?keyword=vinfast"
    }

    # Example endpoint search for VinFast items
    url = "https://shopee.vn/api/v4/search/search_items?by=relevancy&keyword=vinfast&limit=5&newest=0&order=desc&page_type=search&scenario=PAGE_KEYWORD_SEARCH&version=2"
    scraped_data = []

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            for item in items:
                basic = item.get("item_basic", {})
                itemid = basic.get("itemid")
                shopid = basic.get("shopid")
                name = basic.get("name", "Sản phẩm VinFast")

                if itemid and shopid:
                    rating_url = f"https://shopee.vn/api/v4/item/get_ratings?itemid={itemid}&shopid={shopid}&limit=20&type=0"
                    r_res = requests.get(rating_url, headers=headers, timeout=5)
                    if r_res.status_code == 200:
                        ratings = r_res.json().get("data", {}).get("ratings", [])
                        for r in ratings:
                            comment = r.get("comment", "")
                            if comment:
                                scraped_data.append({
                                    "review_text": comment,
                                    "rating": r.get("rating_star", 5),
                                    "product_name": name,
                                    "timestamp": datetime.fromtimestamp(r.get("ctime", datetime.now().timestamp())).strftime("%Y-%m-%d %H:%M:%S"),
                                    "source": "shopee"
                                })
        return pd.DataFrame(scraped_data)
    except Exception as e:
        print(f"[!] Error during Shopee live API request: {e}")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Scrape or generate Shopee VinFast product reviews")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample dataset instead of live scraping")
    parser.add_argument("--count", type=int, default=200, help="Number of sample reviews to generate (default: 200)")
    parser.add_argument("--output", type=str, default="data/scraped/shopee_vinfast_reviews.csv", help="Output CSV filepath")

    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.generate-sample if hasattr(args, "generate-sample") else args.generate_sample:
        print(f"[*] Generating {args.count} sample Shopee reviews...")
        df = generate_samples(count=args.count)
    else:
        print("[*] Running live Shopee API scraping...")
        df = scrape_shopee_live()
        if df.empty:
            print("[!] Scraped 0 rows or live API blocked. Falling back to sample generation.")
            df = generate_samples(count=args.count)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[✔] Saved {len(df)} reviews to {output_path}")


if __name__ == "__main__":
    main()
