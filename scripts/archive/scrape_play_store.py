#!/usr/bin/env python3
"""
Google Play Store Xanh SM app review scraper & sample generator.
App ID: com.xanhsm.passenger
Columns: review_text, rating, thumbs_up, reply_text, timestamp, source='play_store'
"""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

APP_ID = "com.xanhsm.passenger"

TEEN_CODE_APP_REVIEWS = [
    ("app lag qua, mo len xoay xoay hoai ko dat dc xe", 1, 12, "Xanh SM xin chào! Rất tiếc vì trải nghiệm chưa tốt của bạn. Vui lòng cập nhật ứng dụng phiên bản mới nhất nhé."),
    ("tai xe tot, chay em vl, dc r nha", 5, 8, None),
    ("dieu xe nhanh vl, moi bam 1p da thay tai xe den r. 10 diem!", 5, 15, None),
    ("gia re phet, ma km nhieu vl. recommend cho mn dung nha", 5, 23, None),
    ("ui dep vl! xe dien sach se ko mui ti nao, rat ung y", 5, 19, None),
    ("App lag qua hnay ko vao dat xe dc, phai di grab bth", 2, 5, "Chào bạn, Xanh SM đã khắc phục sự cố hệ thống. Bạn thử lại giúp Xanh nhé!"),
    ("Xe xanh SM xịn qua di, tài xế lịch sự nhẹ nhàng tks app", 5, 11, None),
    ("khuyen mai nhieu phet, di xe dien bao ve moitruong dc r nha", 5, 7, None),
    ("dinh vi sai cho ko goi dc tai xe, app ngu vl", 1, 34, "Xanh SM xin lỗi bạn vì bất tiện này. Bạn vui lòng bật GPS độ chính xác cao giúp shop nhé!"),
    ("gia cước ok phet, tai xe nhiet tinh ho tro vali nang", 5, 6, None),
    ("app lag qua hnay ko load dc ban do, mong admin fix som k", 2, 9, "Xanh SM đã ghi nhận thông tin và chuyển bộ phận kỹ thuật xử lý ạ."),
    ("Tài xế chạy mượt vãi luôn, xe ko mui xang xe rat êm", 5, 14, None),
    ("Tai xe tot nma app hay bi diss ra ngoai qua phet", 3, 4, None),
    ("Giao dien app dep vl, de thao tac, dat xe trong 30s", 5, 20, None),
    ("Ko nhan dc ma otp dang nhap, bth lam an kieu j z", 1, 18, "Chào bạn, hãy kiểm tra lại kết nối mạng hoặc thử lại sau 2 phút nhé!"),
    ("Xanh SM Luxury di thich qua di, xe VinFast VF8 sang xin dep", 5, 30, None),
    ("Gia re phet nma gio cao diem hoi kho dat xe ti r nha", 4, 3, None),
    ("App lag qua moi lan chuyen qua vnpay la bi văng out", 2, 8, "Cảm ơn bạn đã phản hồi, Xanh SM đang làm việc với cổng thanh toán để tối ưu ạ."),
    ("Tai xe tot, noi chuyen vui ve, lai xe an toan vl", 5, 16, None),
    ("dc r nha cac ban, xanh sm uy tin phet 5 sao", 5, 5, None),
]

STANDARD_APP_REVIEWS = [
    ("Ứng dụng Xanh SM rất dễ sử dụng, đặt xe nhanh chóng và tiện lợi.", 5, 10, None),
    ("Xe điện VinFast chạy rất êm, không mùi xăng dầu, tài xế lịch sự.", 5, 25, None),
    ("Chất lượng dịch vụ vượt trội so với các hãng xe công nghệ khác.", 5, 18, None),
    ("Đôi lúc ứng dụng bị giật lag khi chọn điểm đến vào giờ cao điểm.", 3, 7, "Xanh SM ghi nhận phản hồi và đang cải thiện hiệu năng app."),
    ("Giá cước rõ ràng, không bị tăng giá vô lý khi trời mưa.", 5, 12, None),
    ("Tính năng đặt xe trước hoạt động rất hiệu quả và chính xác.", 5, 9, None),
    ("Cần cải thiện bản đồ định vị vì nhiều lúc chỉ đường sai cho tài xế.", 3, 15, "Xanh SM cảm ơn góp ý và đang cập nhật dữ liệu bản đồ mới."),
    ("Chăm sóc khách hàng hỗ trợ giải quyết sự cố quên đồ rất nhanh.", 5, 22, None),
    ("Đội ngũ tài xế đào tạo bài bản, thái độ thân thiện chuẩn mực.", 5, 31, None),
    ("App hay bị lỗi không áp dụng được mã giảm giá.", 2, 11, "Chào bạn, bạn vui lòng kiểm tra điều kiện áp dụng mã giảm giá nhé."),
]


def generate_samples(count=500):
    """Generate sample dataset of Play Store reviews for Xanh SM."""
    data = []
    start_date = datetime.now() - timedelta(days=120)

    for i in range(count):
        is_teen = random.random() < 0.40
        if is_teen:
            review_text, rating, thumbs, reply = random.choice(TEEN_CODE_APP_REVIEWS)
        else:
            review_text, rating, thumbs, reply = random.choice(STANDARD_APP_REVIEWS)

        # Add random variations to thumbs_up and timestamps
        thumbs_up = max(0, thumbs + random.randint(-2, 10))
        random_days = random.randint(0, 120)
        random_seconds = random.randint(0, 86400)
        ts = (start_date + timedelta(days=random_days, seconds=random_seconds)).strftime("%Y-%m-%d %H:%M:%S")

        data.append({
            "review_text": review_text,
            "rating": rating,
            "thumbs_up": thumbs_up,
            "reply_text": reply if reply else "",
            "timestamp": ts,
            "source": "play_store"
        })

    return pd.DataFrame(data)


def scrape_play_store_live(limit=200):
    """
    Live scraper using google-play-scraper package.
    """
    try:
        from google_play_scraper import Sort, reviews
    except ImportError:
        print("[!] google-play-scraper is not installed. Please install with `uv add google-play-scraper` or run with `--generate-sample`.")
        return pd.DataFrame()

    print(f"[*] Scraping live Play Store reviews for {APP_ID}...")
    try:
        result, _ = reviews(
            APP_ID,
            lang='vi',
            country='vn',
            sort=Sort.NEWEST,
            count=limit
        )
        data = []
        for r in result:
            data.append({
                "review_text": r.get("content", ""),
                "rating": r.get("score", 5),
                "thumbs_up": r.get("thumbsUpCount", 0),
                "reply_text": r.get("replyContent", "") or "",
                "timestamp": str(r.get("at", datetime.now())),
                "source": "play_store"
            })
        return pd.DataFrame(data)
    except Exception as e:
        print(f"[!] Error during Play Store scrape: {e}")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Scrape or generate Google Play Store Xanh SM reviews")
    parser.add_argument("--generate-sample", action="store_true", help="Generate sample dataset instead of live scraping")
    parser.add_argument("--count", type=int, default=500, help="Number of sample reviews to generate (default: 500)")
    parser.add_argument("--output", type=str, default="data/scraped/play_store_xanhsm_reviews.csv", help="Output CSV filepath")

    args = parser.parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.generate_sample:
        print(f"[*] Generating {args.count} sample Play Store reviews...")
        df = generate_samples(count=args.count)
    else:
        print("[*] Running live Play Store scraping...")
        df = scrape_play_store_live()
        if df.empty:
            print("[!] Scraped 0 rows or library missing. Falling back to sample generation.")
            df = generate_samples(count=args.count)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"[✔] Saved {len(df)} reviews to {output_path}")


if __name__ == "__main__":
    main()
