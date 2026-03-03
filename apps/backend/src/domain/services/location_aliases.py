"""
Location aliases for improved search accuracy.
Maps common Indian location abbreviations, nicknames, and variants to full searchable names.
Works like Google Maps - "HSR" returns "HSR Layout, Bangalore".
"""

from typing import Dict, List, Optional
import re

# Indian location aliases - common abbreviations and nicknames
LOCATION_ALIASES: Dict[str, str] = {
    # ========================================
    # BANGALORE / BENGALURU
    # ========================================
    "hsr": "HSR Layout Bangalore",
    "hsr layout": "HSR Layout Bangalore",
    "btm": "BTM Layout Bangalore",
    "btm layout": "BTM Layout Bangalore",
    "jp nagar": "JP Nagar Bangalore",
    "jpnagar": "JP Nagar Bangalore",
    "jayanagar": "Jayanagar Bangalore",
    "kr market": "KR Market Bangalore",
    "city market": "KR Market Bangalore",
    "mg road": "MG Road Bangalore",
    "brigade road": "Brigade Road Bangalore",
    "whitefield": "Whitefield Bangalore",
    "electronic city": "Electronic City Bangalore",
    "e-city": "Electronic City Bangalore",
    "ecity": "Electronic City Bangalore",
    "koramangala": "Koramangala Bangalore",
    "kormangala": "Koramangala Bangalore",
    "indiranagar": "Indiranagar Bangalore",
    "indira nagar": "Indiranagar Bangalore",
    "marathahalli": "Marathahalli Bangalore",
    "marthahalli": "Marathahalli Bangalore",
    "majestic": "Majestic Bangalore",
    "kempegowda": "Majestic Bus Station Bangalore",
    "silk board": "Silk Board Junction Bangalore",
    "silkboard": "Silk Board Junction Bangalore",
    "hebbal": "Hebbal Bangalore",
    "yelahanka": "Yelahanka Bangalore",
    "rajajinagar": "Rajajinagar Bangalore",
    "rr nagar": "Rajarajeshwari Nagar Bangalore",
    "rrnagar": "Rajarajeshwari Nagar Bangalore",
    "basavanagudi": "Basavanagudi Bangalore",
    "jayanagar 4th block": "Jayanagar 4th Block Bangalore",
    "hal": "HAL Airport Road Bangalore",
    "old airport road": "Old Airport Road Bangalore",
    "sarjapur": "Sarjapur Road Bangalore",
    "bellandur": "Bellandur Bangalore",
    "hosa road": "Hosa Road Bangalore",
    "kr puram": "KR Puram Bangalore",
    "tin factory": "Tin Factory Bangalore",
    "ulsoor": "Ulsoor Bangalore",
    "domlur": "Domlur Bangalore",
    "richmond road": "Richmond Road Bangalore",
    "residency road": "Residency Road Bangalore",
    "cunningham road": "Cunningham Road Bangalore",
    "bannerghatta": "Bannerghatta Road Bangalore",
    "bannerghatta road": "Bannerghatta Road Bangalore",
    "kanakapura": "Kanakapura Road Bangalore",
    "kanakapura road": "Kanakapura Road Bangalore",
    "nagarbhavi": "Nagarbhavi Bangalore",
    "vijayanagar": "Vijayanagar Bangalore",
    "malleshwaram": "Malleshwaram Bangalore",
    "sadashivanagar": "Sadashivanagar Bangalore",
    "ub city": "UB City Bangalore",
    "embassy golf links": "Embassy Golf Links Bangalore",
    "orion mall": "Orion Mall Bangalore",
    "mantri mall": "Mantri Square Mall Bangalore",
    "phoenix mall": "Phoenix Marketcity Bangalore",
    "manyata": "Manyata Tech Park Bangalore",
    "bagmane": "Bagmane Tech Park Bangalore",
    "outer ring road": "Outer Ring Road Bangalore",
    "orr": "Outer Ring Road Bangalore",

    # ========================================
    # DELHI NCR
    # ========================================
    "cp": "Connaught Place Delhi",
    "connaught place": "Connaught Place Delhi",
    "rajiv chowk": "Rajiv Chowk Delhi",
    "ito": "ITO Delhi",
    "rk puram": "RK Puram Delhi",
    "rkpuram": "RK Puram Delhi",
    "south ex": "South Extension Delhi",
    "south extension": "South Extension Delhi",
    "dwarka": "Dwarka Delhi",
    "noida": "Noida Uttar Pradesh",
    "greater noida": "Greater Noida Uttar Pradesh",
    "gurgaon": "Gurugram Haryana",
    "gurugram": "Gurugram Haryana",
    "cyber city": "Cyber City Gurugram",
    "cybercity": "Cyber City Gurugram",
    "dlf": "DLF Cyber City Gurugram",
    "faridabad": "Faridabad Haryana",
    "ghaziabad": "Ghaziabad Uttar Pradesh",
    "nehru place": "Nehru Place Delhi",
    "lajpat nagar": "Lajpat Nagar Delhi",
    "saket": "Saket Delhi",
    "select citywalk": "Select Citywalk Delhi",
    "hauz khas": "Hauz Khas Delhi",
    "hkv": "Hauz Khas Village Delhi",
    "karol bagh": "Karol Bagh Delhi",
    "rohini": "Rohini Delhi",
    "pitampura": "Pitampura Delhi",
    "janakpuri": "Janakpuri Delhi",
    "vasant kunj": "Vasant Kunj Delhi",
    "vasant vihar": "Vasant Vihar Delhi",
    "gk": "Greater Kailash Delhi",
    "greater kailash": "Greater Kailash Delhi",
    "defence colony": "Defence Colony Delhi",
    "def col": "Defence Colony Delhi",
    "lodi road": "Lodhi Road Delhi",
    "lodhi garden": "Lodhi Gardens Delhi",
    "india gate": "India Gate Delhi",
    "red fort": "Red Fort Delhi",
    "chandni chowk": "Chandni Chowk Delhi",
    "paharganj": "Paharganj Delhi",
    "old delhi": "Old Delhi Railway Station Delhi",
    "new delhi": "New Delhi Railway Station",
    "ndls": "New Delhi Railway Station",
    "igi": "IGI Airport Delhi",
    "airport": "Indira Gandhi International Airport Delhi",
    "aerocity": "Aerocity Delhi",
    "mayur vihar": "Mayur Vihar Delhi",
    "preet vihar": "Preet Vihar Delhi",
    "laxmi nagar": "Laxmi Nagar Delhi",
    "nirman vihar": "Nirman Vihar Delhi",
    "rajouri garden": "Rajouri Garden Delhi",
    "rajouri": "Rajouri Garden Delhi",
    "tilak nagar": "Tilak Nagar Delhi",
    "uttam nagar": "Uttam Nagar Delhi",
    "moti nagar": "Moti Nagar Delhi",
    "patel nagar": "Patel Nagar Delhi",
    "shahdara": "Shahdara Delhi",
    "kashmere gate": "Kashmere Gate Delhi",
    "civil lines": "Civil Lines Delhi",

    # ========================================
    # YOGYAKARTA / JOGJA (Indonesia)
    # ========================================
    "jogja": "Yogyakarta Indonesia",
    "jogjakarta": "Yogyakarta Indonesia",
    "yogya": "Yogyakarta Indonesia",
    "malioboro": "Malioboro Yogyakarta",
    "jalan malioboro": "Jalan Malioboro Yogyakarta",
    "kraton": "Kraton Yogyakarta",
    "keraton": "Kraton Yogyakarta",
    "tugu": "Tugu Yogyakarta",
    "tugu jogja": "Tugu Yogyakarta",
    "prawirotaman": "Prawirotaman Yogyakarta",
    "kaliurang": "Kaliurang Sleman Yogyakarta",
    "parangtritis": "Parangtritis Beach Bantul Yogyakarta",
    "prambanan": "Prambanan Temple Yogyakarta",
    "borobudur": "Borobudur Temple Magelang",
    "ugm": "Universitas Gadjah Mada Yogyakarta",
    "gadjah mada": "Universitas Gadjah Mada Yogyakarta",
    "uny": "Universitas Negeri Yogyakarta",
    "amplaz": "Ambarukmo Plaza Yogyakarta",
    "ambarukmo": "Ambarukmo Plaza Yogyakarta",
    "hartono mall": "Hartono Mall Yogyakarta",
    "jcm": "Jogja City Mall Yogyakarta",
    "jogja city mall": "Jogja City Mall Yogyakarta",
    "gejayan": "Jalan Gejayan Yogyakarta",
    "seturan": "Seturan Yogyakarta",
    "babarsari": "Babarsari Yogyakarta",
    "condong catur": "Condong Catur Sleman Yogyakarta",
    "godean": "Godean Sleman Yogyakarta",
    "gamping": "Gamping Sleman Yogyakarta",
    "bantul": "Bantul Yogyakarta",
    "sleman": "Sleman Yogyakarta",
    "kulon progo": "Kulon Progo Yogyakarta",
    "gunung kidul": "Gunung Kidul Yogyakarta",
    "wonosari": "Wonosari Gunung Kidul Yogyakarta",
    "imogiri": "Imogiri Bantul Yogyakarta",
    "kotagede": "Kotagede Yogyakarta",
    "adisucipto": "Adisucipto Airport Yogyakarta",
    "yia": "Yogyakarta International Airport Kulon Progo",

    # ─── Indore / Madhya Pradesh ───
    "rajwada": "Rajwada Palace, Indore",
    "vijay nagar": "Vijay Nagar, Indore",
    "palasia": "Palasia, Indore",
    "sapna sangeeta": "Sapna Sangeeta Road, Indore",
    "bhawarkuan": "Bhawarkuan Square, Indore",
    "chhappan dukan": "Chhappan Dukan (56 Shops), Indore",
    "sarafa bazaar": "Sarafa Bazaar, Indore",
    "khajrana": "Khajrana, Indore",
    "pipliyahana": "Pipliyahana, Indore",
    "rau": "Rau, Indore",
    "mhow": "Mhow (Dr. Ambedkar Nagar), Indore",
    "iim indore": "IIM Indore, Rau",
    "iit indore": "IIT Indore, Simrol",
    "super corridor": "Super Corridor, Indore",
    "ab road": "Agra Bombay Road, Indore",
    "mg road indore": "Mahatma Gandhi Road, Indore",
    "scheme 54": "Scheme No. 54, Indore",
    "scheme 78": "Scheme No. 78, Indore",
    "lalbagh": "Lalbagh Palace, Indore",
    "holkar stadium": "Holkar Cricket Stadium, Indore",
    "treasure island": "Treasure Island Mall, Indore",
    "nehru park indore": "Nehru Park, Indore",
    "gangwal bus stand": "Gangwal Bus Stand, Indore",
    "patalpani": "Patalpani Waterfall, Indore",
    "banganga": "Banganga, Indore",
    "nipania": "Nipania, Indore",
    "musakhedi": "Musakhedi, Indore",
    "juni indore": "Juni Indore (Old Indore)",
    "chhawani": "Chhawani, Indore",
    "silicon city": "Silicon City, Indore",

    # ========================================
    # MUMBAI
    # ========================================
    "bkc": "Bandra Kurla Complex Mumbai",
    "bandra kurla": "Bandra Kurla Complex Mumbai",
    "dadar": "Dadar Mumbai",
    "andheri": "Andheri Mumbai",
    "andheri east": "Andheri East Mumbai",
    "andheri west": "Andheri West Mumbai",
    "powai": "Powai Mumbai",
    "hiranandani": "Hiranandani Gardens Powai Mumbai",
    "worli": "Worli Mumbai",
    "lower parel": "Lower Parel Mumbai",
    "marine drive": "Marine Drive Mumbai",
    "gateway": "Gateway of India Mumbai",
    "colaba": "Colaba Mumbai",
    "juhu": "Juhu Mumbai",
    "juhu beach": "Juhu Beach Mumbai",
    "bandra": "Bandra Mumbai",
    "bandra west": "Bandra West Mumbai",
    "santacruz": "Santacruz Mumbai",
    "vile parle": "Vile Parle Mumbai",
    "goregaon": "Goregaon Mumbai",
    "malad": "Malad Mumbai",
    "kandivali": "Kandivali Mumbai",
    "borivali": "Borivali Mumbai",
    "thane": "Thane Mumbai",
    "navi mumbai": "Navi Mumbai",
    "vashi": "Vashi Navi Mumbai",
    "kharghar": "Kharghar Navi Mumbai",
    "panvel": "Panvel Mumbai",
    "fort": "Fort Mumbai",
    "cst": "Chhatrapati Shivaji Terminus Mumbai",
    "churchgate": "Churchgate Mumbai",
    "nariman point": "Nariman Point Mumbai",
    "cuffe parade": "Cuffe Parade Mumbai",
    "sion": "Sion Mumbai",
    "kurla": "Kurla Mumbai",
    "chembur": "Chembur Mumbai",
    "ghatkopar": "Ghatkopar Mumbai",
    "mulund": "Mulund Mumbai",
    "airoli": "Airoli Mumbai",
    "seepz": "SEEPZ Mumbai",
    "phoenix": "Phoenix Mills Mumbai",
    "high street": "High Street Phoenix Mumbai",

    # ========================================
    # CHENNAI
    # ========================================
    "t nagar": "T Nagar Chennai",
    "tnagar": "T Nagar Chennai",
    "anna nagar": "Anna Nagar Chennai",
    "adyar": "Adyar Chennai",
    "velachery": "Velachery Chennai",
    "ecr": "East Coast Road Chennai",
    "omr": "Old Mahabalipuram Road Chennai",
    "it corridor": "IT Corridor Chennai",
    "sholinganallur": "Sholinganallur Chennai",
    "tambaram": "Tambaram Chennai",
    "porur": "Porur Chennai",
    "vadapalani": "Vadapalani Chennai",
    "koyambedu": "Koyambedu Chennai",
    "egmore": "Egmore Chennai",
    "central": "Chennai Central",
    "mylapore": "Mylapore Chennai",
    "nungambakkam": "Nungambakkam Chennai",
    "mount road": "Mount Road Chennai",
    "marina": "Marina Beach Chennai",
    "besant nagar": "Besant Nagar Chennai",
    "thiruvanmiyur": "Thiruvanmiyur Chennai",
    "guindy": "Guindy Chennai",
    "perungudi": "Perungudi Chennai",
    "tidel park": "Tidel Park Chennai",
    "thoraipakkam": "Thoraipakkam Chennai",
    "express avenue": "Express Avenue Chennai",
    "phoenix chennai": "Phoenix Marketcity Chennai",

    # ========================================
    # HYDERABAD
    # ========================================
    "hitech city": "HITEC City Hyderabad",
    "hitec city": "HITEC City Hyderabad",
    "hi-tech city": "HITEC City Hyderabad",
    "cyber towers": "Cyber Towers Hyderabad",
    "gachibowli": "Gachibowli Hyderabad",
    "kondapur": "Kondapur Hyderabad",
    "madhapur": "Madhapur Hyderabad",
    "jubilee hills": "Jubilee Hills Hyderabad",
    "banjara hills": "Banjara Hills Hyderabad",
    "road no 1": "Road No 1 Banjara Hills Hyderabad",
    "secunderabad": "Secunderabad Hyderabad",
    "kukatpally": "Kukatpally Hyderabad",
    "kphb": "KPHB Colony Hyderabad",
    "ameerpet": "Ameerpet Hyderabad",
    "begumpet": "Begumpet Hyderabad",
    "lb nagar": "LB Nagar Hyderabad",
    "dilsukhnagar": "Dilsukhnagar Hyderabad",
    "charminar": "Charminar Hyderabad",
    "abids": "Abids Hyderabad",
    "himayatnagar": "Himayatnagar Hyderabad",
    "somajiguda": "Somajiguda Hyderabad",
    "uppal": "Uppal Hyderabad",
    "miyapur": "Miyapur Hyderabad",
    "financial district": "Financial District Hyderabad",
    "nanakramguda": "Nanakramguda Hyderabad",
    "shamshabad": "Shamshabad Airport Hyderabad",
    "rgia": "Rajiv Gandhi International Airport Hyderabad",
    "inorbit": "Inorbit Mall Hyderabad",
    "forum mall": "Forum Sujana Mall Hyderabad",

    # ========================================
    # PUNE
    # ========================================
    "fc road": "Fergusson College Road Pune",
    "jm road": "Jangli Maharaj Road Pune",
    "mg road pune": "MG Road Pune",
    "koregaon park": "Koregaon Park Pune",
    "kp": "Koregaon Park Pune",
    "camp": "Camp Pune",
    "kalyani nagar": "Kalyani Nagar Pune",
    "viman nagar": "Viman Nagar Pune",
    "kharadi": "Kharadi Pune",
    "hinjewadi": "Hinjewadi Pune",
    "hinjawadi": "Hinjewadi Pune",
    "baner": "Baner Pune",
    "aundh": "Aundh Pune",
    "wakad": "Wakad Pune",
    "pimpri": "Pimpri Chinchwad Pune",
    "chinchwad": "Pimpri Chinchwad Pune",
    "pcmc": "Pimpri Chinchwad Pune",
    "shivaji nagar": "Shivaji Nagar Pune",
    "deccan": "Deccan Gymkhana Pune",
    "swargate": "Swargate Pune",
    "hadapsar": "Hadapsar Pune",
    "magarpatta": "Magarpatta City Pune",
    "eon": "EON IT Park Pune",
    "phoenix pune": "Phoenix Marketcity Pune",

    # ========================================
    # KOLKATA
    # ========================================
    "park street": "Park Street Kolkata",
    "esplanade": "Esplanade Kolkata",
    "salt lake": "Salt Lake City Kolkata",
    "sector 5": "Sector V Salt Lake Kolkata",
    "new town": "New Town Kolkata",
    "rajarhat": "Rajarhat Kolkata",
    "howrah": "Howrah Kolkata",
    "sealdah": "Sealdah Kolkata",
    "dum dum": "Dum Dum Kolkata",
    "gariahat": "Gariahat Kolkata",
    "ballygunge": "Ballygunge Kolkata",
    "south city": "South City Mall Kolkata",
    "quest mall": "Quest Mall Kolkata",
    "victoria memorial": "Victoria Memorial Kolkata",
}

# Reverse mapping for fuzzy suggestions
REVERSE_ALIASES: Dict[str, List[str]] = {}
for alias, full in LOCATION_ALIASES.items():
    if full not in REVERSE_ALIASES:
        REVERSE_ALIASES[full] = []
    REVERSE_ALIASES[full].append(alias)


def expand_query_with_aliases(query: str) -> str:
    """
    Expand search query with location aliases.
    "HSR" -> "HSR Layout Bangalore"
    "HSR sector 2" -> "HSR Layout sector 2"

    Args:
        query: Original search query

    Returns:
        Expanded query if alias found, otherwise original query
    """
    if not query:
        return query

    query_lower = query.lower().strip()

    # Direct alias match (most common case)
    if query_lower in LOCATION_ALIASES:
        return LOCATION_ALIASES[query_lower]

    # Partial match - e.g., "hsr sector 2" -> "HSR Layout Bangalore sector 2"
    for alias, full_name in sorted(LOCATION_ALIASES.items(), key=lambda x: -len(x[0])):
        if query_lower.startswith(alias + " "):
            remainder = query[len(alias):].strip()
            # Don't include city name twice if remainder has additional context
            base_parts = full_name.split()
            # Remove city name for cleaner expansion
            if len(base_parts) > 1:
                base_without_city = " ".join(base_parts[:-1])
                return f"{base_without_city} {remainder}"
            return f"{full_name} {remainder}"

        # Also check with common connectors
        if query_lower.startswith(alias + ","):
            remainder = query[len(alias)+1:].strip()
            return f"{full_name}, {remainder}"

    return query


def get_alias_suggestions(query: str, max_suggestions: int = 5) -> List[Dict]:
    """
    Get alias-based suggestions for partial queries.

    Args:
        query: Search query
        max_suggestions: Max number of suggestions

    Returns:
        List of suggestion dicts with alias and full_name
    """
    if not query or len(query) < 2:
        return []

    query_lower = query.lower().strip()
    suggestions = []

    for alias, full_name in LOCATION_ALIASES.items():
        # Prefix match
        if alias.startswith(query_lower):
            suggestions.append({
                "alias": alias,
                "full_name": full_name,
                "match_type": "prefix"
            })
        # Substring match
        elif query_lower in alias:
            suggestions.append({
                "alias": alias,
                "full_name": full_name,
                "match_type": "substring"
            })

    # Sort by match quality (prefix matches first, then by alias length)
    suggestions.sort(key=lambda x: (x["match_type"] != "prefix", len(x["alias"])))

    return suggestions[:max_suggestions]


def get_popular_aliases_for_city(city: str) -> List[str]:
    """
    Get popular aliases for a specific city.

    Args:
        city: City name (e.g., "Bangalore", "Delhi")

    Returns:
        List of popular aliases for that city
    """
    city_lower = city.lower()
    aliases = []

    for alias, full_name in LOCATION_ALIASES.items():
        if city_lower in full_name.lower():
            aliases.append(alias)

    return aliases[:20]  # Return top 20
