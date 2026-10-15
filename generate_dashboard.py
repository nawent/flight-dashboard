import os
import csv
import urllib.request
import serpapi
from datetime import datetime, timedelta

# ==============================================================================
# 🎛️ CONFIGURATION HUB (Managed via Google Sheets!)
# ==============================================================================
API_KEY = os.environ.get("SERPAPI_KEY")

WISHLIST_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQSls-dmabSaeWWWTJd4TSu9KEylid0yvgwQZqvkaNcEC4cKl8hSfHW7Fj6pFGvOJ9jiBdHxeroe_f/pub?gid=0&single=true&output=csv"
HOLIDAYS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQSls-dmabSaeWWWTJd4TSu9KEylid0yvgwQZqvkaNcEC4cKl8hSfHW7Fj6pFGvOJ9jiBdHxeroe_f/pub?gid=1128536141&single=true&output=csv"

ORIGIN_CODES = ["BOS", "PVD"]

INTL_REGIONS = [
    {"name": "Europe", "area_id": "/m/02j9z"},
    {"name": "Caribbean", "area_id": "/m/01c1m"},
    {"name": "Central America", "area_id": "/m/01d_p"},
    {"name": "South America", "area_id": "/m/06nm1"},
    {"name": "Canada", "area_id": "/m/0d060g"}
]

INTERNATIONAL_KEYWORDS = [
    "Canada", "Mexico", "Europe", "UK", "France", "Italy", "Spain", "Germany", 
    "London", "Paris", "Rome", "Cancun", "Dublin", "Reykjavik", "Tokyo", "Costa Rica",
    "Bahamas", "Jamaica", "Aruba", "Puerto Vallarta", "Cabo", "Toronto", "Montreal", "Vancouver",
    "Punta Cana", "Santo Domingo", "Bermuda", "Bogota", "Lima", "San Jose", "Lisbon", "Hamilton"
]

LOCATION_LOOKUP = {
    "Hamilton": "Hamilton, Ontario, Canada (YHM/YYZ)",
    "Montreal": "Montréal, Quebec, Canada (YUL)",
    "Toronto": "Toronto, Ontario, Canada (YYZ)",
    "Vancouver": "Vancouver, British Columbia, Canada (YVR)",
    "Waterloo": "Kitchener-Waterloo, Ontario, Canada (YKF)",
    "Calgary": "Calgary, Alberta, Canada (YYC)",
    "Halifax": "Halifax, Nova Scotia, Canada (YHZ)",
    "Windsor": "Windsor, Ontario, Canada (YQG)",
    "Comox": "Comox Valley, British Columbia, Canada (YQQ)",
    "Asheville": "Asheville, North Carolina, USA (AVL)",
    "Boise": "Boise, Idaho, USA (BOI)",
    "London": "London, United Kingdom (LHR/LGW)",
    "Paris": "Paris, France (CDG/ORY)"
}
# ==============================================================================

def get_enhanced_location(destination_name):
    for key, detailed_name in LOCATION_LOOKUP.items():
        if key.lower() in destination_name.lower():
            return detailed_name
    return destination_name

def load_config_from_sheets():
    target_destinations = []
    user_holidays = []
    
    # 1. Load Wishlist Destinations
    try:
        response = urllib.request.urlopen(WISHLIST_CSV_URL)
        lines = [line.decode('utf-8') for line in response.readlines()]
        reader = csv.DictReader(lines)
        for row in reader:
            target_destinations.append({
                "destination": row["destination"].strip(),
                "arrival_id": row["arrival_id"].strip(),
                "is_international": row.get("is_international", "FALSE").strip().upper() == "TRUE"
            })
    except Exception as e:
        print(f"⚠️ Error loading Wishlist sheet: {e}")

    # 2. Load Holidays
    try:
        response = urllib.request.urlopen(HOLIDAYS_CSV_URL)
        lines = [line.decode('utf-8') for line in response.readlines()]
        reader = csv.DictReader(lines)
        for row in reader:
            h_entry = {"name": row["name"].strip()}
            if row.get("date") and row["date"].strip():
                h_entry["date"] = row["date"].strip()
            if row.get("start") and row["start"].strip():
                h_entry["start"] = row["start"].strip()
            if row.get("end") and row["end"].strip():
                h_entry["end"] = row["end"].strip()
            user_holidays.append(h_entry)
    except Exception as e:
        print(f"⚠️ Error loading Holidays sheet: {e}")
        
    return target_destinations, user_holidays

def trip_includes_holiday(trip_start_str, trip_end_str, user_holidays):
    trip_start = datetime.strptime(trip_start_str, "%Y-%m-%d")
    trip_end = datetime.strptime(trip_end_str, "%Y-%m-%d")
    matched_holidays = []
    
    for h in user_holidays:
        if "date" in h:
            h_date = datetime.strptime(h["date"], "%Y-%m-%d")
            if trip_start <= h_date <= trip_end:
                matched_holidays.append(h["name"])
        elif "start" in h and "end" in h:
            h_start = datetime.strptime(h["start"], "%Y-%m-%d")
            h_end = datetime.strptime(h["end"], "%Y-%m-%d")
            if max(trip_start, h_start) <= min(trip_end, h_end):
                matched_holidays.append(h["name"])
                
    return matched_holidays

def check_if_international(destination_name):
    return any(kw.lower() in destination_name.lower() for kw in INTERNATIONAL_KEYWORDS)

def evaluate_price_status(price, category):
    benchmarks = {
        "Dom Short": 160,
        "Dom Long": 180,
        "Intl Short": 380,
        "Intl Long": 450,
        "Wishlist": 300
    }
    threshold = benchmarks.get(category, 250)
    
    if price < threshold * 0.85:
        return "🟢 Below Avg", "price-low"
    elif price <= threshold * 1.15:
        return "🟡 Typical Price", "price-typical"
    else:
        return "🔴 Above Avg", "price-high"

def run_dashboard():
    TARGET_DESTINATIONS, USER_HOLIDAYS = load_config_from_sheets()
    client = serpapi.Client(api_key=API_KEY)
    explore_trips = []
    wishlist_grouped_trips = {target["destination"]: [] for target in TARGET_DESTINATIONS}
    
    # 1A. General Explore Sweeps (BOS & PVD)
    for origin in ORIGIN_CODES:
        for duration_type in ["1", "2"]:
            params = {
                "engine": "google_travel_explore",
                "departure_id": origin,
                "travel_duration": duration_type,
                "currency": "USD"
            }
            try:
                results = client.search(params)
                for dest in results.get("destinations", []):
                    name = dest.get("name", "Unknown Destination")
                    price = dest.get("flight_price")
                    start_str = dest.get("start_date")
                    end_str = dest.get("end_date")
                    if not price or not start_str or not end_str:
                        continue
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    duration = (end_date - start_date).days
                    weekend_cnt = sum(1 for i in range(duration + 1) if (start_date + timedelta(days=i)).weekday() >= 4)
                    hols = trip_includes_holiday(start_str, end_str, USER_HOLIDAYS)
                    is_intl = check_if_international(name)
                    trip_sig = f"{origin}-{name}-{start_str}-{end_str}"

                    if 3 <= duration <= 7 and (weekend_cnt >= 1 or len(hols) > 0):
                        if not any(t["signature"] == trip_sig for t in explore_trips):
                            explore_trips.append({
                                "signature": trip_sig, "origin": origin, "destination": name,
                                "detailed_dest": get_enhanced_location(name),
                                "price": price, "start": start_str, "end": end_str,
                                "duration": duration, "weekend_count": weekend_cnt,
                                "holidays": hols, "is_international": is_intl,
                                "price_insights": None
                            })
            except Exception as e:
                print(f"Error scanning explore for {origin}: {e}")

    # 1B. International Regional Sweeps (BOS & PVD)
    for origin in ORIGIN_CODES:
        for region in INTL_REGIONS:
            for duration_type in ["1", "2"]:
                params = {
                    "engine": "google_travel_explore",
                    "departure_id": origin,
                    "arrival_area_id": region["area_id"],
                    "travel_duration": duration_type,
                    "currency": "USD"
                }
                try:
                    results = client.search(params)
                    for dest in results.get("destinations", []):
                        name = dest.get("name", "Unknown Destination")
                        price = dest.get("flight_price")
                        start_str = dest.get("start_date")
                        end_str = dest.get("end_date")
                        if not price or not start_str or not end_str:
                            continue
                        start_date = datetime.strptime(start_str, "%Y-%m-%d")
                        end_date = datetime.strptime(end_str, "%Y-%m-%d")
                        duration = (end_date - start_date).days
                        weekend_cnt = sum(1 for i in range(duration + 1) if (start_date + timedelta(days=i)).weekday() >= 4)
                        hols = trip_includes_holiday(start_str, end_str, USER_HOLIDAYS)
                        trip_sig = f"{origin}-{name}-{start_str}-{end_str}"

                        if 3 <= duration <= 7 and (weekend_cnt >= 1 or len(hols) > 0):
                            if not any(t["signature"] == trip_sig for t in explore_trips):
                                explore_trips.append({
                                    "signature": trip_sig, "origin": origin, "destination": name,
                                    "detailed_dest": get_enhanced_location(name),
                                    "price": price, "start": start_str, "end": end_str,
                                    "duration": duration, "weekend_count": weekend_cnt,
                                    "holidays": hols, "is_international": True,
                                    "price_insights": None
                                })
                except Exception as e:
                    print(f"Error sweeping {region['name']} for {origin}: {e}")

    # 2. Target Wishlist Routes (Sweeps BOTH BOS and PVD automatically!)
    for target in TARGET_DESTINATIONS:
        dest_key = target["destination"]
        if dest_key not in wishlist_grouped_trips:
            wishlist_grouped_trips[dest_key] = []

        today = datetime.now()
        sample_dates = [
            (today + timedelta(days=30), today + timedelta(days=34)),
            (today + timedelta(days=60), today + timedelta(days=64)),
            (today + timedelta(days=90), today + timedelta(days=94)),
            (today + timedelta(days=120), today + timedelta(days=124)),
            (datetime(2026, 11, 12), datetime(2026, 11, 16))
        ]

        for origin in ORIGIN_CODES:
            for out_date, ret_date in sample_dates:
                out_str = out_date.strftime("%Y-%m-%d")
                ret_str = ret_date.strftime("%Y-%m-%d")
                f_params = {
                    "engine": "google_flights", "departure_id": origin,
                    "arrival_id": target["arrival_id"], "type": "1",
                    "outbound_date": out_str, "return_date": ret_str,
                    "currency": "USD"
                }
                try:
                    res = client.search(f_params)
                    options = res.get("best_flights", []) + res.get("other_flights", [])
                    p_insights = res.get("price_insights", {})
                    
                    if options:
                        cheapest = min(options, key=lambda x: x.get("price", float('inf')))
                        price = cheapest.get("price")
                        duration = (ret_date - out_date).days
                        weekend_cnt = sum(1 for i in range(duration + 1) if (out_date + timedelta(days=i)).weekday() >= 4)
                        hols = trip_includes_holiday(out_str, ret_str, USER_HOLIDAYS)
                        t_sig = f"{origin}-{dest_key}-{out_str}-{ret_str}"
                        
                        if not any(t["signature"] == t_sig for t in wishlist_grouped_trips[dest_key]):
                            wishlist_grouped_trips[dest_key].append({
                                "signature": t_sig, "origin": origin, "destination": dest_key,
                                "detailed_dest": get_enhanced_location(dest_key),
                                "price": price, "start": out_str, "end": ret_str,
                                "duration": duration, "weekend_count": weekend_cnt,
                                "holidays": hols, "price_insights": p_insights
                            })
                except Exception as e:
                    print(f"Error checking {origin} -> {dest_key}: {e}")

    # Sort wishlist options for each destination by price across both airports
    for dest in wishlist_grouped_trips:
        wishlist_grouped_trips[dest].sort(key=lambda x: x["price"])

    # Categorize & Sort General Explore Lists
    dom_short = sorted([t for t in explore_trips if not t["is_international"] and 3 <= t["duration"] <= 5], key=lambda x: x["price"])
    dom_long  = sorted([t for t in explore_trips if not t["is_international"] and 6 <= t["duration"] <= 7], key=lambda x: x["price"])
    intl_short = sorted([t for t in explore_trips if t["is_international"] and 3 <= t["duration"] <= 5], key=lambda x: x["price"])
    intl_long  = sorted([t for t in explore_trips if t["is_international"] and 6 <= t["duration"] <= 7], key=lambda x: x["price"])

    # Generate HTML Output
    os.makedirs("public", exist_ok=True)
    now_str = datetime.now().strftime("%B %d, %Y at %I:%M %p EST")

    def render_cards(trips, category_label, limit=15):
        if not trips:
            return "<p class='no-data'>No active deals found matching this category right now.</p>"
        html = ""
        for t in trips[:limit]:
            hol_badge = f"<span class='badge hol'>🇺🇸 {', '.join(t['holidays'])}</span>" if t['holidays'] else ""
            
            p_insights = t.get("price_insights")
            if p_insights and p_insights.get("price_level"):
                level = p_insights.get("price_level", "").lower()
                low_r = p_insights.get("typical_price_range", [None, None])[0]
                high_r = p_insights.get("typical_price_range", [None, None])[1]
                range_str = f" (Typical: ${low_r}–${high_r})" if low_r and high_r else ""
                
                if level == "low":
                    price_badge = f"<span class='badge price-low'>🟢 Below Avg{range_str}</span>"
                elif level == "high":
                    price_badge = f"<span class='badge price-high'>🔴 Above Avg{range_str}</span>"
                else:
                    price_badge = f"<span class='badge price-typical'>🟡 Typical Price{range_str}</span>"
            else:
                label_text, badge_class = evaluate_price_status(t["price"], category_label)
                price_badge = f"<span class='badge {badge_class}'>{label_text}</span>"

            html += f"""
            <div class='card'>
                <div class='card-header'>
                    <span class='route'>{t['origin']} <span class='arrow'>➡️</span> {t['detailed_dest']}</span>
                    <span class='price'>${t['price']}</span>
                </div>
                <div class='card-details'>
                    <span>📅 {t['start']} to {t['end']} ({t['duration']} days)</span>
                    <span>🗓️ {t['weekend_count']} Weekend Days</span>
                    {price_badge}
                    {hol_badge}
                </div>
            </div>
            """
        return html

    # Render Individual Wishlist Sections
    wishlist_sections_html = ""
    if not wishlist_grouped_trips:
        wishlist_sections_html = "<p class='no-data'>No wishlist destinations added yet. Update your Google Sheet wishlist!</p>"
    else:
        for dest_name, trips in wishlist_grouped_trips.items():
            enhanced_name = get_enhanced_location(dest_name)
            cards_html = render_cards(trips, "Wishlist", limit=5)
            wishlist_sections_html += f"""
            <div class='section'>
                <h2>🎯 Target Destination: {enhanced_name}</h2>
                {cards_html}
            </div>
            """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Flight Intelligence Dashboard</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #0f172a;
                --bg-card: #1e293b;
                --bg-card-hover: #334155;
                --border-color: #334155;
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --accent-blue: #38bdf8;
                --glow-price: #38bdf8;
            }}
            
            * {{
                box-sizing: border-box;
            }}

            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: var(--bg-main);
                color: var(--text-main);
                margin: 0;
                padding: 24px 16px;
                line-height: 1.5;
            }}

            .container {{
                max-width: 920px;
                margin: 0 auto;
            }}

            header {{
                text-align: center;
                margin-bottom: 32px;
                padding: 10px 0;
            }}

            h1 {{
                margin: 0;
                color: var(--text-main);
                font-size: 32px;
                font-weight: 800;
                letter-spacing: -0.025em;
                background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}

            .last-updated {{
                font-size: 13px;
                color: var(--text-muted);
                margin-top: 6px;
                font-weight: 500;
            }}

            .section {{
                background: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 16px;
                padding: 24px;
                margin-bottom: 24px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            }}

            h2 {{
                margin-top: 0;
                font-size: 20px;
                font-weight: 700;
                border-bottom: 1px solid var(--border-color);
                padding-bottom: 14px;
                color: #e2e8f0;
                letter-spacing: -0.01em;
            }}

            .card {{
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 12px;
                background: #0f172a;
                transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
            }}

            .card:hover {{
                transform: translateY(-2px);
                border-color: #475569;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
            }}

            .card-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-weight: 700;
                font-size: 16px;
                flex-wrap: wrap;
                gap: 12px;
            }}

            .route {{
                color: #f1f5f9;
            }}

            .arrow {{
                color: var(--accent-blue);
                font-size: 14px;
            }}

            .price {{
                color: var(--accent-blue);
                font-size: 22px;
                font-weight: 800;
                text-shadow: 0 0 12px rgba(56, 189, 248, 0.3);
            }}

            .card-details {{
                margin-top: 12px;
                font-size: 13.5px;
                color: var(--text-muted);
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                align-items: center;
            }}

            .badge {{
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 700;
                display: inline-flex;
                align-items: center;
                gap: 4px;
            }}

            .badge.hol {{
                background: rgba(245, 158, 11, 0.15);
                color: #fbbf24;
                border: 1px solid rgba(245, 158, 11, 0.3);
            }}

            .badge.price-low {{
                background: rgba(16, 185, 129, 0.15);
                color: #34d399;
                border: 1px solid rgba(16, 185, 129, 0.3);
            }}

            .badge.price-typical {{
                background: rgba(148, 163, 184, 0.15);
                color: #cbd5e1;
                border: 1px solid rgba(148, 163, 184, 0.3);
            }}

            .badge.price-high {{
                background: rgba(239, 68, 68, 0.15);
                color: #f87171;
                border: 1px solid rgba(239, 68, 68, 0.3);
            }}

            .no-data {{
                color: var(--text-muted);
                font-style: italic;
                margin: 8px 0 0 0;
            }}

            @media (max-width: 600px) {{
                body {{ padding: 16px 8px; }}
                .section {{ padding: 16px; border-radius: 12px; }}
                h1 {{ font-size: 24px; }}
                .card-header {{ flex-direction: column; align-items: flex-start; gap: 4px; }}
                .price {{ font-size: 20px; }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>✈️ Flight Intelligence Dashboard</h1>
                <div class="last-updated">Updated Daily | Last Scan: {now_str}</div>
            </header>

            <!-- Dynamic Wishlist Cards per Destination -->
            {wishlist_sections_html}

            <div class="section">
                <h2>🇺🇸 General: Domestic Quick Getaways (3–5 Days)</h2>
                {render_cards(dom_short, "Dom Short")}
            </div>

            <div class="section">
                <h2>🌴 General: Domestic Week-Long Trips (6–7 Days)</h2>
                {render_cards(dom_long, "Dom Long")}
            </div>

            <div class="section">
                <h2>✈️ General: International Quick Getaways (3–5 Days)</h2>
                {render_cards(intl_short, "Intl Short")}
            </div>

            <div class="section">
                <h2>🌍 General: International Week-Long Trips (6–7 Days)</h2>
                {render_cards(intl_long, "Intl Long")}
            </div>
        </div>
    </body>
    </html>
    """

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    run_dashboard()
