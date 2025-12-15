
import pandas as pd
import numpy as np

APP_NAME_MAP = {
    "com.kakao.talk": "카카오톡",
    "com.instagram.android": "인스타그램",
    "com.twitter.android": "트위터",
    "com.discord": "디스코드",
    "com.google.android.youtube": "유튜브",
    "com.everytime.v2": "에브리타임",
    "com.geode.launcher": "지오메트리 대시",
    "gg.dak.bser": "이터널 리턴",
    "com.robtopx.geometryjump": "지오메트리 점프",
    "com.riotgames.league.teamfighttactics": "TFT",
    "com.kurogame.wutheringwaves.global": "명조",
    "com.spotify.music": "스포티파이",
    "com.netflix.mediaclient": "넷플릭스",
    "com.nhn.android.webtoon": "네이버 웹툰",
    "com.android.chrome": "크롬",
    "notion.id": "노션",
    "com.samsung.android.app.notes": "삼성 노트",
    "com.coupang.mobile": "쿠팡",
    "com.nhn.android.nmap": "네이버 지도",
    "com.samsung.android.dialer": "알람",
    "com.samsung.android.incallui": "통화",
    "com.sec.android.app.camera": "카메라",
    "com.sec.android.gallery3d": "갤러리",
    "com.sec.android.app.launcher": "홈",
    "com.android.settings": "설정",
    "com.samsung.android.easysetup": "에이지 셋업",
    "com.kakaopay.app": "카카오페이"
}

def get_app_name(pkg):
    return APP_NAME_MAP.get(pkg, pkg) # Fallback to package name if not found

def analyze_patterns(usage_data, emotion_data):
    """
    Returns: list of dicts {title, content}
    """
    result_list = []
    
    if not usage_data or not emotion_data:
        return [{"title": "데이터 부족", "content": "분석할 데이터가 충분하지 않습니다."}]

    df_usage = pd.DataFrame(usage_data)
    df_emotion = pd.DataFrame(emotion_data)
    
    df_usage['date_str'] = df_usage['date'].astype(str)
    df_emotion['date_str'] = df_emotion['date'].astype(str)

    merged = pd.merge(df_usage, df_emotion, on='date_str', how='inner')
    
    if merged.empty:
        return [{"title": "데이터 부족", "content": "분석할 데이터가 부족합니다."}]

    merged['minutes'] = merged['duration_ms'] / 1000 / 60
    
    # Pre-calculate App Names if possible
    if 'package_name' in merged.columns:
        merged['app_name'] = merged['package_name'].apply(get_app_name)
    else:
        # Fallback if package_name missing (should not happen with updated service)
        merged['app_name'] = merged['category']

    # 1. Emotion -> App Usage Correlation (Specific Apps)
    # We want to find specific apps that spike for specific emotions.
    # Group by [emotion, app_name] -> avg minutes
    # Compare with global avg for that app
    
    # Filter only significant usage apps (e.g. > 5 min avg daily usage globally) to avoid noise
    # Global avg per app (across all days)
    # Note: Global avg should be "Sum of usage / Count of unique days"
    unique_days = merged['date_str'].nunique()
    app_global_sum = merged.groupby('app_name')['minutes'].sum()
    app_global_avg = app_global_sum / unique_days
    
    # Filter apps with > 5 mins avg daily
    major_apps = app_global_avg[app_global_avg > 5].index.tolist()
    
    df_major = merged[merged['app_name'].isin(major_apps)]
    
    if not df_major.empty:
        # Emotion Avg uses only days with that emotion.
        # But for correct comparison, we should divide sum by "Count of days with that emotion"
        # Not just groupby mean directly because if an app wasn't used on a day, it's 0, but groupby mean might skip it if row doesn't exist?
        # Actually merged has rows only for usage. Ideally we need to fill 0s for missing days.
        # Strict way: Pivot date x app, fill 0, then merge emotion, then group.
        
        pivot = merged.pivot_table(index='date_str', columns='app_name', values='minutes', aggfunc='sum', fill_value=0)
        # Merge emotion back
        pivot = pivot.merge(df_emotion[['date_str', 'emotion']], on='date_str', how='left')
        
        for app in pivot.columns:
            if app in ['date_str', 'emotion']: continue
            if app not in major_apps: continue
            
            global_mean = pivot[app].mean()
            if global_mean < 5: continue # Skip minor apps
            
            for emo in ['GOOD', 'NORMAL', 'BAD']:
                emo_data = pivot[pivot['emotion'] == emo]
                if emo_data.empty: continue
                
                emo_mean = emo_data[app].mean()
                
                diff_pct = 0
                if global_mean > 0:
                    diff_pct = (emo_mean - global_mean) / global_mean * 100
                
                # Check significance
                if diff_pct > 30: # 30% increase
                    # Determine category for Title (rough heuristic)
                    # We can find category from original df
                    cat = merged[merged['app_name'] == app]['category'].iloc[0]
                    cat_map = {"SNS": "SNS", "GAME": "게임", "OTHER": "기타 앱"}
                    cat_name = cat_map.get(cat, "앱")
                    
                    title = f"[{emo} 기분일 때 {cat_name} 사용 ↑]"
                    # Translate Emotion for Korean context
                    emo_kr_map = {"GOOD": "기분이 좋을", "NORMAL": "평범한", "BAD": "기분이 좋지 않을"}
                    emo_kr = emo_kr_map.get(emo, emo)
                    
                    content = f"{emo_kr} 때에는 {app} 사용량이 평소보다 약 {int(diff_pct)}% 증가했습니다."
                    result_list.append({"title": title, "content": content})
                    
    # Limit number of patterns
    # Prioritize higher pct?
    
    # 2. Time -> Usage (Concentration)
    # "Which hour has the highest usage for specific apps?"
    if 'hour' not in merged.columns and 'start_time' in merged.columns:
         # Similar parsing logic
         first_val = merged['start_time'].iloc[0]
         if isinstance(first_val, str):
            merged['hour'] = pd.to_datetime(merged['start_time']).dt.hour
         else:
            merged['datetime'] = pd.to_datetime(merged['start_time'], errors='coerce')
            merged['hour'] = merged['datetime'].dt.hour

    if 'hour' in merged.columns:
        valid_time = merged.dropna(subset=['hour'])
        if not valid_time.empty:
            # Group by [hour, app_name]
            # Identify "Peak Hour" for major apps
            hour_app = valid_time.groupby(['hour', 'app_name'])['minutes'].sum().reset_index()
            
            # For each major app, find peak hour
            for app in major_apps:
                app_data = hour_app[hour_app['app_name'] == app]
                if app_data.empty: continue
                
                peak_row = app_data.loc[app_data['minutes'].idxmax()]
                peak_h = int(peak_row['hour'])
                peak_min = peak_row['minutes']
                
                # Check if this hour is significantly higher than others?
                # Simply report the peak period
                # Title: [20-21시 집중 사용]
                title = f"[{peak_h}시-{peak_h+1}시 집중 사용]"
                content = f"{app}은(는) 주로 {peak_h}시에서 {peak_h+1}시 사이에 가장 많이 사용됩니다."
                
                # Deduplicate: if we already have a similar pattern? 
                # Maybe just add it.
                # Filter out obvious ones or limit.
                
                # Let's add only if it's really concentrated (e.g. > 20% of total usage of that app?)
                total_app_usage = app_data['minutes'].sum()
                if peak_min / total_app_usage > 0.15: # > 15% in one hour
                     result_list.append({"title": title, "content": content})

    # Return top 3-5 distinct patterns
    # Shuffle or Sort? Sort by some confidence?
    # Simple limit
    return result_list[:5]
