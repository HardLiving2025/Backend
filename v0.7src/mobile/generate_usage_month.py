import json
import random
from datetime import datetime, timedelta

# Common apps found in usage_week.json
APPS = [
    "com.kakao.talk",
    "com.sec.android.app.launcher",
    "com.google.android.youtube",
    "com.instagram.android",
    "com.nhn.android.webtoon",
    "com.geode.launcher",
    "com.spotify.music",
    "com.android.chrome",
    "com.samsung.android.dialer",
    "com.samsung.android.incallui",
    "com.sec.android.gallery3d",
    "com.nhn.android.nmap",
    "com.coupang.mobile",
    "gg.dak.bser",
    "com.netflix.mediaclient",
    "com.twitter.android"
]

def generate_month_data(start_date_str, days=30):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    data = []

    for day_offset in range(days):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        # 48 slots per day (00:00 to 23:30)
        for hour in range(24):
            for minute in [0, 30]:
                time_slot = f"{hour:02d}:{minute:02d}"
                
                # Determine usage probability based on time of day
                # Night (01:00 - 06:00): Low probability
                # Day: High probability
                if 1 <= hour < 6:
                    usage_prob = 0.1
                else:
                    usage_prob = 0.8

                if random.random() > usage_prob:
                    continue

                # Generate usage for this slot
                usage_breakdown = {}
                total_ms = 0
                max_ms = 30 * 60 * 1000 # 30 mins in ms

                # Pick 1-5 random apps
                num_apps = random.randint(1, 5)
                selected_apps = random.sample(APPS, num_apps)

                for app in selected_apps:
                    if total_ms >= max_ms:
                        break
                    
                    # Random duration remaining
                    remaining_ms = max_ms - total_ms
                    duration = random.randint(1000, remaining_ms) // num_apps
                    
                    if duration > 0:
                        usage_breakdown[app] = duration
                        total_ms += duration

                if usage_breakdown:
                    data.append({
                        "usage_date": date_str,
                        "time_slot": time_slot,
                        "package": usage_breakdown
                    })

    return data

if __name__ == "__main__":
    # Start from a reasonable date, e.g., Nov 1, 2025
    month_data = generate_month_data("2025-11-01", days=30)
    
    output_path = "usage_month.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(month_data, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {len(month_data)} records in {output_path}")
