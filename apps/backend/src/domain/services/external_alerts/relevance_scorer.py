"""
Relevance Scorer - Filters news for Delhi-specific flood/waterlogging relevance.

This is the MOST CRITICAL component for ensuring high-quality alerts.
Precision over recall: Better to miss some articles than show irrelevant ones.

Usage:
    scorer = DelhiFloodRelevanceScorer()
    score, reason = scorer.score(title="Delhi waterlogging...", body="...")
    if score >= 0.7:
        # Show to user - HIGH QUALITY
    elif score >= 0.4:
        # Show with lower priority - MEDIUM QUALITY
    else:
        # Reject silently - LOW QUALITY or IRRELEVANT
"""

import re
from typing import Tuple, List, Set
import logging

logger = logging.getLogger(__name__)


class DelhiFloodRelevanceScorer:
    """
    Scores news articles for Delhi-specific flood relevance.

    Scoring Strategy:
    - Score >= 0.7: HIGH QUALITY - show to user
    - Score 0.4-0.7: MEDIUM - show with lower priority
    - Score < 0.4: LOW - reject

    Title is heavily weighted because:
    - "Delhi Waterlogging..." is clearly relevant
    - "India Weather Update..." mentioning Delhi in body is less specific
    """

    # Delhi location keywords - comprehensive list
    DELHI_LOCATIONS = {
        "exact": ["delhi", "new delhi"],
        "regions": [
            "ncr", "national capital region", "national capital",
            "north delhi", "south delhi", "east delhi", "west delhi", "central delhi",
            "north west delhi", "south west delhi", "south east delhi", "north east delhi",
            "shahdara", "new delhi district"
        ],
        "areas": [
            "dwarka", "rohini", "pitampura", "janakpuri", "vikaspuri",
            "laxmi nagar", "mayur vihar", "preet vihar", "vasant kunj",
            "saket", "hauz khas", "defence colony", "lajpat nagar",
            "connaught place", "karol bagh", "paharganj", "chandni chowk",
            "rajouri garden", "tilak nagar", "uttam nagar", "palam",
            "narela", "bawana", "mundka", "najafgarh", "kapashera",
            "okhla", "sarita vihar", "jasola", "nehru place",
            "ghazipur", "anand vihar", "shahdara", "seelampur"
        ],
        "landmarks": [
            "yamuna", "yamuna river", "yamuna floodplain",
            "minto bridge", "ito underpass", "pul prahladpur",
            "mehrauli-badarpur", "mehrauli badarpur road",
            "najafgarh drain", "najafgarh nala",
            "ring road", "inner ring road", "outer ring road",
            "pragati maidan", "india gate", "red fort",
            "nizamuddin", "lodhi road", "ashram", "mathura road"
        ],
        "authorities": [
            "mcd", "north mcd", "south mcd", "east mcd",
            "pwd delhi", "delhi pwd", "public works department delhi",
            "djb", "delhi jal board", "jal board",
            "ndmc", "new delhi municipal council",
            "dda", "delhi development authority",
            "delhi government", "delhi govt", "aap government",
            "arvind kejriwal", "atishi", "delhi cm"
        ],
        "ncr_cities": [
            "noida", "greater noida", "ghaziabad",
            "gurgaon", "gurugram", "faridabad"
        ]
    }

    # Flood/waterlogging keywords by signal strength
    FLOOD_KEYWORDS = {
        "high_signal": [
            "waterlog", "waterlogging", "waterlogged", "water logging",
            "flood", "flooded", "flooding", "floods",
            "inundat", "inundated", "inundation",
            "submerge", "submerged", "submersion",
            "deluge", "deluged",
            "knee-deep", "knee deep", "waist-deep", "waist deep",
            "chest-deep", "chest deep"
        ],
        "medium_signal": [
            "heavy rain", "heavy rainfall", "heavy rains",
            "cloudburst", "cloud burst",
            "downpour", "torrential rain", "torrential rainfall",
            "rain havoc", "rain fury", "rain chaos",
            "traffic jam", "traffic chaos", "traffic disruption",
            "road closure", "roads closed", "road blocked",
            "stranded", "marooned", "trapped",
            "rescue", "rescued", "evacuation", "evacuated",
            "water enters", "water entered", "water logging"
        ],
        "low_signal": [
            "rain", "rainfall", "rains", "rainy",
            "monsoon", "monsoon rain",
            "storm", "thunderstorm",
            "alert", "warning", "advisory",
            "imd", "met department"
        ]
    }

    # HARD REJECT: Other Indian cities' flood news (unless Delhi also mentioned)
    REJECT_PATTERNS = [
        ("mumbai", "flood"), ("mumbai", "waterlog"),
        ("chennai", "flood"), ("chennai", "waterlog"),
        ("kolkata", "flood"), ("kolkata", "waterlog"),
        ("kerala", "flood"), ("kerala", "rain"),
        ("bangalore", "flood"), ("bengaluru", "flood"),
        ("hyderabad", "flood"), ("hyderabad", "rain"),
        ("assam", "flood"), ("assam", "rain"),
        ("bihar", "flood"), ("bihar", "rain"),
        ("gujarat", "flood"), ("gujarat", "rain"),
        ("odisha", "flood"), ("odisha", "rain"),
        ("rajasthan", "flood"), ("rajasthan", "rain"),
        ("madhya pradesh", "flood"), ("mp flood",),
        ("uttar pradesh", "flood"),  # Unless specifically about Delhi-NCR
        ("pune", "flood"), ("pune", "rain"),
        ("ahmedabad", "flood"), ("surat", "flood"),
    ]

    def __init__(self):
        # Pre-compile location patterns for efficiency
        self._all_locations: Set[str] = set()
        for category in self.DELHI_LOCATIONS.values():
            self._all_locations.update(category)

        self._high_signal_keywords: Set[str] = set(self.FLOOD_KEYWORDS["high_signal"])
        self._medium_signal_keywords: Set[str] = set(self.FLOOD_KEYWORDS["medium_signal"])
        self._low_signal_keywords: Set[str] = set(self.FLOOD_KEYWORDS["low_signal"])

    def score(self, title: str, body: str) -> Tuple[float, str]:
        """
        Score an article for Delhi flood relevance.

        Args:
            title: Article headline/title
            body: Article body/description text

        Returns:
            Tuple of (score 0.0-1.0, reason string)
        """
        title_lower = title.lower().strip()
        body_lower = body.lower().strip() if body else ""
        full_text = f"{title_lower} {body_lower}"

        # Step 1: HARD REJECT - Other cities' flood news without Delhi
        for pattern in self.REJECT_PATTERNS:
            if len(pattern) == 2:
                city, keyword = pattern
                if city in full_text and keyword in full_text:
                    if not self._has_delhi_mention(full_text):
                        return 0.0, f"Rejected: {city} {keyword} without Delhi mention"
            elif len(pattern) == 1:
                if pattern[0] in full_text and not self._has_delhi_mention(full_text):
                    return 0.0, f"Rejected: {pattern[0]} without Delhi mention"

        # Step 2: Check title for Delhi + flood keywords
        title_has_delhi = self._has_delhi_in_text(title_lower)
        title_has_flood_high = self._has_flood_keyword(title_lower, "high")
        title_has_flood_medium = self._has_flood_keyword(title_lower, "medium")

        # Step 3: Check body for Delhi + flood keywords
        body_delhi_score = self._location_score(full_text)
        body_flood_score = self._flood_keyword_score(full_text)

        # Step 4: Calculate final score based on where keywords appear

        # Best case: Title has both Delhi AND flood keyword
        if title_has_delhi and title_has_flood_high:
            return 0.95, "Title: Delhi + high-signal flood keyword"

        if title_has_delhi and title_has_flood_medium:
            return 0.85, "Title: Delhi + medium-signal flood keyword"

        # Good case: Title has Delhi, flood in body
        if title_has_delhi:
            if body_flood_score >= 0.5:
                return 0.75 + (body_flood_score * 0.15), f"Title: Delhi, body flood={body_flood_score:.2f}"
            else:
                return 0.6, "Title: Delhi only, weak flood signal in body"

        # Acceptable: Title has flood keyword, Delhi prominent in body
        if title_has_flood_high and body_delhi_score >= 0.5:
            return 0.7 + (body_delhi_score * 0.1), f"Title: flood, body Delhi={body_delhi_score:.2f}"

        if title_has_flood_medium and body_delhi_score >= 0.6:
            return 0.6 + (body_delhi_score * 0.1), f"Title: rain/disruption, body Delhi={body_delhi_score:.2f}"

        # Lower quality: Both only in body
        if body_delhi_score > 0 and body_flood_score > 0:
            combined = (body_delhi_score * 0.5) + (body_flood_score * 0.4)
            if combined >= 0.5:
                return combined * 0.7, f"Body only: Delhi={body_delhi_score:.2f}, flood={body_flood_score:.2f}"
            return combined * 0.5, f"Weak body signals: Delhi={body_delhi_score:.2f}, flood={body_flood_score:.2f}"

        # No relevant signals found
        return 0.0, "No Delhi flood signals found"

    def _has_delhi_mention(self, text: str) -> bool:
        """Check if text mentions Delhi at all."""
        return "delhi" in text or "ncr" in text

    def _has_delhi_in_text(self, text: str) -> bool:
        """Check if text has any Delhi location keyword."""
        for loc in self.DELHI_LOCATIONS["exact"]:
            if loc in text:
                return True
        for loc in self.DELHI_LOCATIONS["regions"]:
            if loc in text:
                return True
        for loc in self.DELHI_LOCATIONS["areas"]:
            if loc in text:
                return True
        return False

    def _has_flood_keyword(self, text: str, level: str) -> bool:
        """Check if text has flood keywords of given level."""
        keywords = self.FLOOD_KEYWORDS.get(f"{level}_signal", [])
        return any(kw in text for kw in keywords)

    def _location_score(self, text: str) -> float:
        """
        Score text for Delhi location mentions (0.0 to 1.0).
        Higher score = more/stronger Delhi mentions.
        """
        score = 0.0

        # Exact matches are strongest
        for loc in self.DELHI_LOCATIONS["exact"]:
            if loc in text:
                score += 0.4
                break  # Don't double count "delhi" and "new delhi"

        # Region/district mentions
        region_count = sum(1 for loc in self.DELHI_LOCATIONS["regions"] if loc in text)
        score += min(region_count * 0.15, 0.3)

        # Specific area mentions (shows specificity)
        area_count = sum(1 for loc in self.DELHI_LOCATIONS["areas"] if loc in text)
        score += min(area_count * 0.1, 0.2)

        # Landmarks (very specific)
        landmark_count = sum(1 for loc in self.DELHI_LOCATIONS["landmarks"] if loc in text)
        score += min(landmark_count * 0.15, 0.3)

        # Authority mentions (official Delhi context)
        auth_count = sum(1 for loc in self.DELHI_LOCATIONS["authorities"] if loc in text)
        score += min(auth_count * 0.1, 0.2)

        # NCR cities (partial credit)
        ncr_count = sum(1 for loc in self.DELHI_LOCATIONS["ncr_cities"] if loc in text)
        score += min(ncr_count * 0.1, 0.2)

        return min(score, 1.0)

    def _flood_keyword_score(self, text: str) -> float:
        """
        Score text for flood/waterlogging keywords (0.0 to 1.0).
        Higher score = more/stronger flood signals.
        """
        score = 0.0

        # High signal keywords are strongest
        high_count = sum(1 for kw in self.FLOOD_KEYWORDS["high_signal"] if kw in text)
        score += min(high_count * 0.25, 0.5)

        # Medium signal keywords
        medium_count = sum(1 for kw in self.FLOOD_KEYWORDS["medium_signal"] if kw in text)
        score += min(medium_count * 0.15, 0.35)

        # Low signal keywords (minimal contribution)
        low_count = sum(1 for kw in self.FLOOD_KEYWORDS["low_signal"] if kw in text)
        score += min(low_count * 0.05, 0.15)

        return min(score, 1.0)

    def filter_alerts(
        self,
        alerts: list,
        min_score: float = 0.7,
        title_field: str = "title",
        body_field: str = "message"
    ) -> list:
        """
        Filter a list of alert objects by relevance score.

        Args:
            alerts: List of alert objects/dicts
            min_score: Minimum score to include (default 0.7 for HIGH quality)
            title_field: Field name for title in alert object
            body_field: Field name for body/message in alert object

        Returns:
            Filtered list of alerts that meet the minimum score
        """
        filtered = []
        for alert in alerts:
            # Get title and body from alert (handle both dict and object)
            if isinstance(alert, dict):
                title = alert.get(title_field, "")
                body = alert.get(body_field, "")
            else:
                title = getattr(alert, title_field, "")
                body = getattr(alert, body_field, "")

            score, reason = self.score(title, body)

            if score >= min_score:
                # Add score metadata if possible
                if isinstance(alert, dict):
                    alert["_relevance_score"] = score
                    alert["_relevance_reason"] = reason
                filtered.append(alert)
            else:
                logger.debug(f"[RelevanceScorer] Rejected (score={score:.2f}): {title[:60]}... ({reason})")

        return filtered


class BangaloreFloodRelevanceScorer:
    """
    Placeholder for Bangalore-specific scoring.
    Can be implemented similarly to DelhiFloodRelevanceScorer.
    """

    BANGALORE_LOCATIONS = {
        "exact": ["bangalore", "bengaluru"],
        "areas": [
            "koramangala", "indiranagar", "whitefield", "electronic city",
            "marathahalli", "bellandur", "sarjapur", "hsr layout",
            "jp nagar", "jayanagar", "basavanagudi", "rajajinagar",
            "malleshwaram", "hebbal", "yelahanka", "devanahalli"
        ],
        "landmarks": [
            "outer ring road", "orr", "silk board",
            "bellandur lake", "varthur lake", "ulsoor lake"
        ]
    }

    def score(self, title: str, body: str) -> Tuple[float, str]:
        """Placeholder - implement similar to Delhi scorer."""
        # For now, use simple keyword matching
        text = f"{title} {body}".lower()

        has_bangalore = any(loc in text for loc in self.BANGALORE_LOCATIONS["exact"])
        has_flood = any(kw in text for kw in ["flood", "waterlog", "rain", "inundat"])

        if has_bangalore and has_flood:
            return 0.7, "Bangalore + flood keyword"
        elif has_bangalore:
            return 0.4, "Bangalore only"
        return 0.0, "No Bangalore signals"


class YogyakartaFloodRelevanceScorer:
    """
    Relevance scorer for Yogyakarta, Indonesia flood alerts.
    Covers DIY (Daerah Istimewa Yogyakarta) province including
    Sleman, Bantul, Kulon Progo, and Gunung Kidul regencies.
    """

    YOGYAKARTA_LOCATIONS = {
        "exact": ["yogyakarta", "jogjakarta", "jogja", "yogya", "diy"],
        "areas": [
            "bantul", "sleman", "kulon progo", "kulonprogo", "gunung kidul",
            "gunungkidul", "malioboro", "kraton", "tugu", "prawirotaman",
            "kaliurang", "parangtritis", "prambanan", "godean", "gamping",
            "depok sleman", "mlati", "ngaglik", "pakem", "turi",
            "kalasan", "berbah", "ngemplak", "cangkringan",
            "kotagede", "umbulharjo", "mergangsan", "gondokusuman",
        ],
        "rivers": [
            "kali code", "kali opak", "sungai progo", "kali gajah wong",
            "kali winongo", "kali bedog", "kali kuning", "sungai opak",
        ],
        "landmarks": [
            "merapi", "gunung merapi", "mount merapi",
            "borobudur", "malioboro street", "tugu jogja",
        ]
    }

    FLOOD_KEYWORDS_ID = [
        "banjir", "genangan", "longsor", "lahar", "sungai",
        "luapan", "tanggul", "rob", "drainase", "hujan lebat",
    ]

    FLOOD_KEYWORDS_EN = [
        "flood", "waterlog", "inundat", "landslide", "lahar",
        "overflow", "rain", "deluge", "submerge",
    ]

    AUTHORITY_KEYWORDS = [
        "bpbd", "bmkg", "bnpb", "pupr", "pemda diy",
        "pu diy", "basarnas", "sar", "tagana",
    ]

    def score(self, title: str, body: str) -> Tuple[float, str]:
        """Score article relevance for Yogyakarta flooding."""
        text = f"{title} {body}".lower()
        score = 0.0
        reasons = []

        # Location signals
        has_exact = any(loc in text for loc in self.YOGYAKARTA_LOCATIONS["exact"])
        has_area = any(loc in text for loc in self.YOGYAKARTA_LOCATIONS["areas"])
        has_river = any(r in text for r in self.YOGYAKARTA_LOCATIONS["rivers"])

        # Flood signals (bilingual)
        has_flood_id = any(kw in text for kw in self.FLOOD_KEYWORDS_ID)
        has_flood_en = any(kw in text for kw in self.FLOOD_KEYWORDS_EN)
        has_flood = has_flood_id or has_flood_en

        # Authority signals
        has_authority = any(auth in text for auth in self.AUTHORITY_KEYWORDS)

        if has_exact:
            score += 0.4
            reasons.append("Yogyakarta exact match")
        if has_area:
            score += 0.3
            reasons.append("Yogyakarta area match")
        if has_river:
            score += 0.3
            reasons.append("Yogyakarta river match")
        if has_flood:
            score += 0.3
            reasons.append("flood keyword")
        if has_authority:
            score += 0.1
            reasons.append("authority keyword")

        # Lahar from Merapi is a special high-priority signal
        if "merapi" in text and ("lahar" in text or "erupsi" in text):
            score += 0.2
            reasons.append("Merapi volcanic flood risk")

        score = min(score, 1.0)
        reason = " + ".join(reasons) if reasons else "No Yogyakarta signals"
        return score, reason


def get_scorer_for_city(city: str):
    """
    Factory function to get the appropriate scorer for a city.

    Args:
        city: City identifier (e.g., "delhi", "bangalore", "yogyakarta")

    Returns:
        Appropriate relevance scorer instance
    """
    city_lower = city.lower()
    if city_lower == "delhi":
        return DelhiFloodRelevanceScorer()
    elif city_lower in ["bangalore", "bengaluru"]:
        return BangaloreFloodRelevanceScorer()
    elif city_lower in ["yogyakarta", "jogjakarta", "jogja"]:
        return YogyakartaFloodRelevanceScorer()
    else:
        # Default to Delhi scorer (most comprehensive)
        logger.warning(f"No specific scorer for city '{city}', using Delhi scorer")
        return DelhiFloodRelevanceScorer()


# Test function for development
def test_scorer():
    """Test the relevance scorer with sample headlines."""
    scorer = DelhiFloodRelevanceScorer()

    test_cases = [
        # Should score HIGH (>= 0.7)
        ("Delhi Waterlogging: Several areas submerged after heavy rain", "Multiple areas in the capital saw severe waterlogging"),
        ("Heavy rain causes waterlogging in Delhi-NCR, traffic hit", "Commuters faced difficulties as roads flooded"),
        ("ITO underpass flooded as monsoon hits Delhi", "The underpass was closed for traffic"),
        ("Yamuna water level rises in Delhi after heavy rainfall", "Officials monitoring the situation"),

        # Should score MEDIUM (0.4-0.7)
        ("Heavy rain in north India causes disruption", "Delhi and other states saw waterlogging"),
        ("Monsoon update: Rain expected across NCR", "IMD issues advisory for Delhi region"),

        # Should score LOW or REJECT (< 0.4)
        ("Mumbai floods: Waterlogging reported in multiple areas", "Heavy rain lashed the city"),
        ("Kerala floods: Rescue operations underway", "Thousands evacuated"),
        ("India weather update: Rain across multiple states", "Various regions affected"),
        ("Stock markets fall amid rain concerns", "Some mention of Delhi somewhere"),
    ]

    print("Testing DelhiFloodRelevanceScorer:\n" + "="*60)
    for title, body in test_cases:
        score, reason = scorer.score(title, body)
        quality = "HIGH" if score >= 0.7 else "MEDIUM" if score >= 0.4 else "LOW/REJECT"
        print(f"\n[{quality}] Score: {score:.2f}")
        print(f"Title: {title}")
        print(f"Reason: {reason}")
    print("\n" + "="*60)


if __name__ == "__main__":
    test_scorer()
