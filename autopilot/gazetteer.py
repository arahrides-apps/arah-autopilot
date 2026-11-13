"""Where in Jamaica is a photo? Nearest known place to a phone's GPS point. (lat, lon, name, parish, coastal)"""
import math
PLACES = [
    (18.4762, -77.8939, "Montego Bay", "St James", True), (18.5030, -77.9140, "Montego Bay Hip Strip", "St James", True),
    (18.2700, -78.3500, "Negril", "Westmoreland", True), (18.2650, -78.3600, "Seven Mile Beach, Negril", "Westmoreland", True),
    (18.2490, -78.3790, "Negril cliffs", "Westmoreland", True), (18.2290, -78.3650, "Rick's Cafe, West End", "Westmoreland", True),
    (18.4050, -77.1030, "Ocho Rios", "St Ann", True), (18.3740, -77.1450, "Dunn's River Falls", "St Ann", True),
    (18.4090, -77.0300, "Ocho Rios", "St Ann", True), (18.4060, -77.1050, "Fern Gully", "St Ann", False),
    (18.4300, -77.2000, "Discovery Bay", "St Ann", True), (18.4690, -77.6550, "Falmouth", "Trelawny", True),
    (18.4000, -77.1400, "St Ann", "St Ann", True), (18.1800, -76.4500, "Port Antonio", "Portland", True),
    (18.1900, -76.4300, "Blue Lagoon, Portland", "Portland", True), (18.2230, -76.4170, "Winnifred Beach, Portland", "Portland", True),
    (18.1800, -76.3500, "Boston Bay, Portland", "Portland", True), (18.1100, -76.4000, "Reach Falls, Portland", "Portland", False),
    (17.9714, -76.7936, "Kingston", "Kingston", False), (17.9900, -76.7900, "Devon House, Kingston", "St Andrew", False),
    (18.0050, -76.7860, "New Kingston", "St Andrew", False), (17.9390, -76.7870, "Port Royal", "Kingston", True),
    (17.9400, -76.7560, "Palisadoes", "Kingston", True), (17.9200, -76.8300, "Lime Cay, Kingston Harbour", "Kingston", True),
    (18.0100, -76.7400, "Blue Mountains foothills", "St Andrew", False), (18.0400, -76.6000, "Blue Mountains", "St Thomas", False),
    (17.9050, -76.9000, "Portmore", "St Catherine", True), (17.9900, -77.0000, "Spanish Town", "St Catherine", False),
    (18.0400, -77.5000, "Mandeville", "Manchester", False), (18.0450, -77.5030, "Mandeville", "Manchester", False),
    (18.1700, -77.4400, "Christiana", "Manchester", False), (17.8790, -77.7650, "Treasure Beach", "St Elizabeth", True),
    (17.8600, -77.7300, "Lovers Leap, St Elizabeth", "St Elizabeth", True), (18.0350, -77.8450, "Middle Quarters", "St Elizabeth", False),
    (18.0200, -77.8500, "Black River", "St Elizabeth", True), (18.1130, -77.7380, "Holland Bamboo, St Elizabeth", "St Elizabeth", False),
    (18.2000, -77.6600, "YS Falls", "St Elizabeth", False), (18.2250, -77.6400, "Maggotty", "St Elizabeth", False),
    (18.2200, -77.3500, "Cockpit Country", "Trelawny", False), (18.2600, -77.5000, "Montpelier", "St James", False),
    (18.1300, -78.1500, "Savanna-la-Mar", "Westmoreland", True), (18.0400, -76.4100, "Morant Bay", "St Thomas", True),
    (17.8900, -77.2400, "May Pen", "Clarendon", False), (17.8600, -77.3700, "Lionel Town", "Clarendon", False),
    (18.4200, -77.8500, "Lucea", "Hanover", True), (18.3900, -78.1300, "Lucea", "Hanover", True),
    (18.3500, -77.6000, "Albert Town", "Trelawny", False), (18.4300, -77.4000, "Runaway Bay", "St Ann", True),
    (18.3500, -77.3700, "Moneague", "St Ann", False), (18.2900, -77.8500, "Mount Salem area", "St James", False),
    (18.3700, -77.1500, "Mammee Bay", "St Ann", True), (18.1000, -77.2800, "Spanish Town road", "St Catherine", False),
    (18.4600, -77.3300, "Salem, St Ann", "St Ann", True),
]
BBOX = (17.65, 18.60, -78.45, -76.10)      # lat min/max, lon min/max: Jamaica

def in_jamaica(lat, lon):
    return BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]

def km(a, b, c, d):
    p = math.pi / 180; x = (c - a) * p; y = (d - b) * p * math.cos((a + c) / 2 * p)
    return 6371 * math.hypot(x, y)

def nearest(lat, lon, max_km=14):
    """(name, parish, coastal, distance_km) of the closest known place, or None when nothing is within max_km."""
    best = min(((km(lat, lon, la, lo), n, pa, co) for la, lo, n, pa, co in PLACES), default=None)
    if best and best[0] <= max_km:
        return best[1], best[2], best[3], round(best[0], 1)
    return None
