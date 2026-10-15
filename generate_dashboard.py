import os
import csv
import json
import urllib.request
import serpapi
from datetime import datetime, timedelta

# ==============================================================================
# 🎛️ CONFIGURATION HUB
# ==============================================================================
API_KEY = os.environ.get("SERPAPI_KEY")

WISHLIST_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQSls-dmabSaeWWWTJd4TSu9KEylid0yvgwQZqvkaNcEC4cKl8hSfHW7Fj6pFGvOJ9jiBdHxeroe_f/pub?gid=0&single=true&output=csv"
HOLIDAYS_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQSls-dmabSaeWWWTJd4TSu9KEylid0yvgwQZqvkaNcEC4cKl8hSfHW7Fj6pFGvOJ9jiBdHxeroe_f/pub?gid=1128536141&single=true&output=csv"
BLACKLIST_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQQSls-dmabSaeWWWTJd4TSu9KEylid0yvgwQZqvkaNcEC4cKl8hSfHW7Fj6pFGvOJ9jiBdHxeroe_f/pubhtml?gid=212482962&single=true"

ORIGIN_CODES = ["BOS", "PVD"]
BLACKLIST_DESTINATIONS = ["Hamilton", "Waterloo"]

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
    "Punta Cana", "Santo Domingo", "Bermuda", "Bogota", "Lima", "San Jose", "Lisbon"
]

LOCATION_LOOKUP = {
    "Pittsburgh": "Pittsburgh, Pennsylvania, USA (PIT)",
    "Miami": "Miami, Florida, USA (MIA)",
    "Des Moines": "Des Moines, Iowa, USA (DSM)",
    "Asheville": "Asheville, North Carolina, USA (AVL)",
    "Boise": "Boise, Idaho, USA (BOI)",
    "Orlando": "Orlando, Florida, USA (MCO)",
    "Tampa": "Tampa, Florida, USA (TPA)",
    "Fort Lauderdale": "Fort Lauderdale, Florida, USA (FLL)",
    "Denver": "Denver, Colorado, USA (DEN)",
    "Phoenix": "Phoenix, Arizona, USA (PHX)",
    "Las Vegas": "Las Vegas, Nevada, USA (LAS)",
    "Los Angeles": "Los Angeles, California, USA (LAX)",
    "San Francisco": "San Francisco, California, USA (SFO)",
    "Seattle": "Seattle, Washington, USA (SEA)",
    "Austin": "Austin, Texas, USA (AUS)",
    "Nashville": "Nashville, Tennessee, USA (BNA)",
    "New Orleans": "New Orleans, Louisiana, USA (MSY)",
    "Chicago": "Chicago, Illinois, USA (ORD/MDW)",
    "Atlanta": "Atlanta, Georgia, USA (ATL)",
    "Dublin": "Dublin, Ireland (DUB)",
    "Reykjavik": "Reykjavík, Iceland (KEF)",
    "London": "London, United Kingdom (LHR/LGW)",
    "Paris": "Paris, France (CDG/ORY)",
    "Rome": "Rome, Italy (FCO)",
    "Barcelona": "Barcelona, Spain (BCN)",
    "Madrid": "Madrid, Spain (MAD)",
    "Amsterdam": "Amsterdam, Netherlands (AMS)",
    "Lisbon": "Lisbon, Portugal (LIS)",
    "Cancun": "Cancún, Mexico (CUN)",
    "San José del Cabo": "Los Cabos, Mexico (SJD)",
    "Montreal": "Montréal, Quebec, Canada (YUL)",
    "Toronto": "Toronto, Ontario, Canada (YYZ)",
    "Vancouver": "Vancouver, British Columbia, Canada (YVR)",
    "Calgary": "Calgary, Alberta, Canada (YYC)",
    "Halifax": "Halifax, Nova Scotia, Canada (YHZ)"
}

def get_enhanced_location(destination_name, raw_country=""):
    for key, detailed_name in LOCATION_LOOKUP.items():
        if key.lower() in destination_name.lower():
            return detailed_name
    if raw_country:
        return f"{destination_name}, {raw_country}"
    elif check_if_international(destination_name):
        return f"{destination_name} (International)"
    else:
        return f"{destination_name}, USA"

def load_config_from_sheets():
    target_destinations = []
    user_holidays = []
    blacklisted = list(BLACKLIST_DESTINATIONS)
    
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

    if BLACKLIST_CSV_URL and "PASTE_" not in BLACKLIST_CSV_URL:
        try:
            response = urllib.request.urlopen(BLACKLIST_CSV_URL)
            lines = [line.decode('utf-8') for line in response.readlines()]
            reader = csv.DictReader(lines)
            for row in reader:
                dest = row.get("destination", "").strip()
                if dest and dest not in blacklisted:
                    blacklisted.append(dest)
        except Exception as e:
            print(f"⚠️ Error loading Blacklist sheet: {e}")
        
    return target_destinations, user_holidays, blacklisted

def is_blacklisted(destination_name, blacklist):
    return any(b.lower() in destination_name.lower() for b in blacklist)

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
        return "🟢 Below Avg", "price-low", "#059669"
    elif price <= threshold * 1.15:
        return "🟡 Typical Price", "price-typical", "#d97706"
    else:
        return "🔴 Above Avg", "price-high", "#dc2626"

def run_dashboard():
    TARGET_DESTINATIONS, USER_HOLIDAYS, BLACKLIST = load_config_from_sheets()
    client = serpapi.Client(api_key=API_KEY)
    explore_trips = []
    wishlist_grouped_trips = {target["destination"]: [] for target in TARGET_DESTINATIONS}
    all_calendar_events = []
    
    # 1A. General Explore Sweeps
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
                    if is_blacklisted(name, BLACKLIST):
                        continue
                    
                    price = dest.get("flight_price")
                    start_str = dest.get("start_date")
                    end_str = dest.get("end_date")
                    country = dest.get("country", "")
                    if not price or not start_str or not end_str:
                        continue
                    start_date = datetime.strptime(start_str, "%Y-%m-%d")
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                    duration = (end_date - start_date).days
                    weekend_cnt = sum(1 for i in range(duration + 1) if (start_date + timedelta(days=i)).weekday() >= 4)
                    hols = trip_includes_holiday(start_str, end_str, USER_HOLIDAYS)
                    is_intl = check_if_international(name) or (country and country.lower() != "united states")
                    trip_sig = f"{origin}-{name}-{start_str}-{end_str}"

                    if 3 <= duration <= 7 and (weekend_cnt >= 1 or len(hols) > 0):
                        if not any(t["signature"] == trip_sig for t in explore_trips):
                            explore_trips.append({
                                "signature": trip_sig, "origin": origin, "destination": name,
                                "detailed_dest": get_enhanced_location(name, country),
                                "price": price, "start": start_str, "end": end_str,
                                "duration": duration, "weekend_count": weekend_cnt,
                                "holidays": hols, "is_international": is_intl,
                                "price_insights": None
                            })
            except Exception as e:
                print(f"Error scanning explore for {origin}: {e}")

    # 1B. International Regional Sweeps
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
                        if is_blacklisted(name, BLACKLIST):
                            continue
                        
                        price = dest.get("flight_price")
                        start_str = dest.get("start_date")
                        end_str = dest.get("end_date")
                        country = dest.get("country", "")
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
                                    "detailed_dest": get_enhanced_location(name, country),
                                    "price": price, "start": start_str, "end": end_str,
                                    "duration": duration, "weekend_count": weekend_cnt,
                                    "holidays": hols, "is_international": True,
                                    "price_insights": None
                                })
                except Exception as e:
                    print(f"Error sweeping {region['name']} for {origin}: {e}")

    # 2. Target Wishlist Routes
    for target in TARGET_DESTINATIONS:
        dest_key = target["destination"]
        if is_blacklisted(dest_key, BLACKLIST):
            continue

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

    for dest in wishlist_grouped_trips:
        wishlist_grouped_trips[dest].sort(key=lambda x: x["price"])

    dom_short = sorted([t for t in explore_trips if not t["is_international"] and 3 <= t["duration"] <= 5], key=lambda x: x["price"])
    dom_long  = sorted([t for t in explore_trips if not t["is_international"] and 6 <= t["duration"] <= 7], key=lambda x: x["price"])
    intl_short = sorted([t for t in explore_trips if t["is_international"] and 3 <= t["duration"] <= 5], key=lambda x: x["price"])
    intl_long  = sorted([t for t in explore_trips if t["is_international"] and 6 <= t["duration"] <= 7], key=lambda x: x["price"])

    # Aggregate all trips into FullCalendar Event JSON
    all_trips = dom_short + dom_long + intl_short + intl_long
    for dest, trips in wishlist_grouped_trips.items():
        all_trips.extend(trips)

    for t in all_trips:
        cat_label = "Wishlist" if t["destination"] in wishlist_grouped_trips else ("Intl" if t["is_international"] else "Dom")
        label_text, badge_class, color_hex = evaluate_price_status(t["price"], cat_label)
        
        # Calendar end date is exclusive in FullCalendar, so add 1 day for multi-day visual spanning
        end_date_dt = datetime.strptime(t["end"], "%Y-%m-%d") + timedelta(days=1)
        
        all_calendar_events.append({
            "title": f"{t['origin']} → {t['destination']} (${t['price']})",
            "start": t["start"],
            "end": end_date_dt.strftime("%Y-%m-%d"),
            "backgroundColor": color_hex,
            "borderColor": color_hex,
            "extendedProps": {
                "full_dest": t["detailed_dest"],
                "price": f"${t['price']}",
                "status": label_text,
                "duration": f"{t['duration']} days",
                "origin": t["origin"],
                "holidays": ", ".join(t["holidays"]) if t["holidays"] else "None"
            }
        })

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
                label_text, badge_class, _ = evaluate_price_status(t["price"], category_label)
                price_badge = f"<span class='badge {badge_class}'>{label_text}</span>"

            html += f"""
            <div class='card'>
                <div class='card-header'>
                    <span class='route'>{t['origin']} ➡️ {t['detailed_dest']}</span>
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

    regions_str = ", ".join([r["name"] for r in INTL_REGIONS])
    targets_str = ", ".join([t["destination"] for t in TARGET_DESTINATIONS]) if TARGET_DESTINATIONS else "None"
    blacklist_str = ", ".join(BLACKLIST) if BLACKLIST else "None"
    calendar_events_json = json.dumps(all_calendar_events)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Flight Intelligence Dashboard</title>
        <!-- FullCalendar Bundle -->
        <script src="https://cdn.jsdelivr.net/npm/fullcalendar@6.1.8/index.global.min.js"></script>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            header {{ text-align: center; margin-bottom: 20px; }}
            h1 {{ margin: 0; color: #f8fafc; font-size: 28px; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
            .last-updated {{ font-size: 14px; color: #94a3b8; margin-top: 5px; }}
            
            /* Tab Navigation */
            .tabs {{ display: flex; gap: 10px; justify-content: center; margin-bottom: 20px; }}
            .tab-btn {{ background: #1e293b; color: #94a3b8; border: 1px solid #334155; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 15px; transition: all 0.2s; }}
            .tab-btn.active {{ background: #38bdf8; color: #0f172a; border-color: #38bdf8; }}
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}

            /* Calendar Styling */
            #calendar {{ background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
            .fc-theme-standard td, .fc-theme-standard th {{ border-color: #334155 !important; }}
            .fc .fc-toolbar-title {{ color: #f8fafc; font-size: 20px; }}
            .fc .fc-button-primary {{ background-color: #334155; border-color: #475569; color: #f8fafc; }}
            .fc .fc-button-primary:hover {{ background-color: #38bdf8; border-color: #38bdf8; color: #0f172a; }}
            .fc-daygrid-day-number {{ color: #cbd5e1; text-decoration: none !important; }}

            /* Cards Styling */
            .section {{ background: #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 1px solid #334155; }}
            h2 {{ margin-top: 0; font-size: 20px; border-bottom: 1px solid #334155; padding-bottom: 10px; color: #38bdf8; }}
            .card {{ border: 1px solid #334155; border-radius: 8px; padding: 14px; margin-bottom: 10px; background: #0f172a; }}
            .card-header {{ display: flex; justify-content: space-between; font-weight: bold; font-size: 16px; flex-wrap: wrap; gap: 8px; }}
            .price {{ color: #38bdf8; font-size: 20px; text-shadow: 0 0 10px rgba(56,189,248,0.2); }}
            .card-details {{ margin-top: 8px; font-size: 14px; color: #cbd5e1; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
            .badge {{ border-radius: 4px; padding: 3px 8px; font-size: 12px; font-weight: bold; }}
            .badge.hol {{ background: #78350f; color: #fef3c7; border: 1px solid #b45309; }}
            .badge.price-low {{ background: #064e3b; color: #a7f3d0; border: 1px solid #059669; }}
            .badge.price-typical {{ background: #334155; color: #e2e8f0; border: 1px solid #475569; }}
            .badge.price-high {{ background: #7f1d1d; color: #fecaca; border: 1px solid #dc2626; }}
            .no-data {{ color: #64748b; font-style: italic; }}
            footer {{ margin-top: 30px; font-size: 13px; color: #94a3b8; border-top: 1px solid #334155; padding-top: 15px; line-height: 1.6; }}
            footer h3 {{ margin: 0 0 8px 0; font-size: 14px; color: #cbd5e1; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>✈️ Flight Intelligence Dashboard</h1>
                <div class="last-updated">Updated Daily | Last Scan: {now_str}</div>
            </header>

            <div class="tabs">
                <button class="tab-btn active" onclick="switchTab('listView')">📋 List View</button>
                <button class="tab-btn" onclick="switchTab('calendarView')">📅 Calendar View</button>
            </div>

            <!-- TAB 1: LIST VIEW -->
            <div id="listView" class="tab-content active">
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

            <!-- TAB 2: CALENDAR VIEW -->
            <div id="calendarView" class="tab-content">
                <div id="calendar"></div>
            </div>

            <footer>
                <h3>🔍 Active Scan Coverage & Parameters</h3>
                <div>• <strong>Origin Airports:</strong> {', '.join(ORIGIN_CODES)}</div>
                <div>• <strong>International Regional Sweeps:</strong> {regions_str}</div>
                <div>• <strong>Wishlist Targets:</strong> {targets_str}</div>
                <div>• <strong>Excluded / Blacklisted Destinations:</strong> {blacklist_str}</div>
            </footer>
        </div>

        <script>
            let calendarInstance = null;

            function switchTab(tabId) {{
                document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
                document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
                
                document.getElementById(tabId).classList.add('active');
                event.currentTarget.classList.add('active');

                if (tabId === 'calendarView' && !calendarInstance) {{
                    initCalendar();
                }}
            }}

            function initCalendar() {{
                const calendarEl = document.getElementById('calendar');
                calendarInstance = new FullCalendar.Calendar(calendarEl, {{
                    initialView: 'dayGridMonth',
                    headerToolbar: {{
                        left: 'prev,next today',
                        center: 'title',
                        right: 'dayGridMonth,timeGridWeek'
                    }},
                    events: {calendar_events_json},
                    eventClick: function(info) {{
                        const props = info.event.extendedProps;
                        alert(
                            "✈️ " + props.origin + " → " + props.full_dest + "\\n" +
                            "💰 Price: " + props.price + " (" + props.status + ")\\n" +
                            "⏱️ Duration: " + props.duration + "\\n" +
                            "🇺🇸 Holidays Covered: " + props.holidays
                        );
                    }}
                }});
                calendarInstance.render();
            }}
        </script>
    </body>
    </html>
    """

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    run_dashboard()
