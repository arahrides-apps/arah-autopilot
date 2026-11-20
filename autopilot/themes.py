"""What to search for, and what a photo must show, so every picture is from Jamaica and fits the words next to it.
THEMES: a topic (road trip, food, couples...) -> search queries + words the photo description must contain.
ATTRACTIONS: a town/city -> its real attractions, so a Kingston post gets Devon House or the Art Walk, not a random beach."""
import re

# A photo's description must say it is Jamaica (a place name, an attraction, or the word itself).
JA = re.compile(r"jamaica|jamaican|kingston|montego|negril|ocho rios|port antonio|portland|blue mountain|treasure beach|dunn|reggae|rasta|marley|ackee|jerk|blue hole|"
                r"st\.? ann|mandeville|black river|ys falls|y\.s\.|bamboo avenue|holland bamboo|reach falls|mayfield|martha brae|rick'?s|seven mile|doctor'?s cave|"
                r"devon house|emancipation|port royal|hellshire|lime cay|boston bay|frenchman|fern gully|konoko|mystic mountain|appleton|bob marley|trench town|"
                r"falmouth|runaway bay|discovery bay|bluefields|whitehouse|hope gardens|nine mile|rio grande|somerset falls|winnifred|pelican bar|lovers leap|cockpit|accompong|"
                r"sangster|norman manley|ian fleming|rose hall|hip strip|devon|jah|dancehall|ska\b", re.I)

ATTRACTIONS = {
    "kingston": ["Kingston Art Walk", "downtown Kingston skyline", "Emancipation Park Kingston", "Devon House Kingston", "Bob Marley Museum Kingston", "Trench Town Kingston",
                 "Hope Gardens Kingston", "Port Royal Jamaica", "Lime Cay Kingston", "National Gallery Jamaica", "Blue Mountains Kingston view"],
    "ocho rios": ["Ocho Rios town", "Dunn's River Falls", "Fern Gully Ocho Rios", "Blue Hole Ocho Rios", "Mystic Mountain Ocho Rios", "Konoko Falls", "Ocho Rios Jamaica beach", "Green Grotto Caves"],
    "montego bay": ["Montego Bay Hip Strip", "Doctor's Cave Beach Montego Bay", "Rose Hall Great House", "Montego Bay Jamaica", "Martha Brae river rafting", "Montego Bay waterfront"],
    "negril": ["Negril Seven Mile Beach", "Rick's Cafe Negril", "Negril lighthouse", "Negril sunset", "Negril cliffs", "Mayfield Falls"],
    "port antonio": ["Blue Lagoon Port Antonio", "Reach Falls Portland", "Frenchman's Cove Portland", "Boston Bay Jamaica", "Rio Grande rafting Port Antonio", "Port Antonio Jamaica", "Winnifred Beach"],
    "treasure beach": ["Treasure Beach Jamaica", "Pelican Bar Jamaica", "YS Falls Jamaica", "Black River safari Jamaica", "Lovers Leap Jamaica", "Bamboo Avenue Jamaica"],
    "mandeville": ["Mandeville Jamaica town", "Mandeville Manchester Jamaica hills", "Bamboo Avenue Jamaica", "Holland Bamboo Jamaica", "Jamaica countryside hills", "Black River Jamaica"],
    "blue mountains": ["Blue Mountains Jamaica coffee", "Blue Mountain Jamaica view", "Blue Mountain coffee farm Jamaica", "Holywell Blue Mountains"],
    "st ann": ["Discovery Bay Jamaica", "Runaway Bay Jamaica", "St Ann Jamaica", "Nine Mile Bob Marley"],
}

# theme -> (queries, regex the photo description must match, people allowed)
THEMES = {
    "xmas": (["Jamaica Christmas", "Jamaica Christmas Grand Market", "Jamaica Christmas family beach", "Jamaica sorrel Christmas drink", "Jamaica Christmas lights Kingston",
              "Jamaica Jonkanoo", "Jamaica family reunion holiday", "Jamaica Christmas dinner"],
             r"christmas|xmas|santa|grand market|sorrel|jonkanoo|holiday|lights|family|reunion|gift|festive", True),
    "fashion": (["Jamaica fashion week runway", "Jamaica fashion show models", "Ocho Rios fashion", "Jamaican designer runway"],
                r"fashion|runway|model|designer|style", True),
    "tennis": (["tennis court Jamaica", "tennis Montego Bay", "Half Moon Jamaica tennis", "tennis court tropical Jamaica"],
               r"tennis|court|racquet|net", False),
    "road": (["Holland Bamboo Jamaica", "Reach Falls Jamaica", "Jamaica highway road", "Jamaica road trip", "Jamaica roadside fruit stand", "Jamaica coconut water vendor",
              "Bamboo Avenue Jamaica", "Jamaica countryside road", "Jamaica mountain road", "Jamaica roadside jerk stand"],
             r"road|highway|bamboo|route|drive|fruit|coconut|vendor|stand|roadside|falls|countryside|mountain|hill|village|market", True),
    "food": (["bun and cheese Jamaica", "Jamaica jerk chicken", "Jamaican patty", "ackee and saltfish", "Jamaica fruit vendor", "Jamaica coconut water", "Jamaica river cooking food",
              "Jamaica street food", "Jamaican breakfast", "Jamaica roadside jerk", "juicy beef patty close up", "Jamaican beef patty cheese coco bread", "jerk pit smoke Jamaica", "jerk shack Boston Bay"],
             r"bun|cheese|jerk|patty|ackee|saltfish|fruit|coconut|food|cook|market|vendor|stand|breakfast|dish|fish|festival|rice", True),
    "river": (["Jamaica river people swimming", "Jamaica river cooking friends", "Jamaica waterfall swimming people", "Jamaica river rafting", "Jamaica riverside picnic"],
              r"river|falls|waterfall|swim|raft|cook|picnic|pool|creek", True),
    "culture": (["Jamaica reggae music", "Jamaica Rastafari culture", "Jamaica street art", "Jamaica dancehall", "Jamaica carnival", "Jamaica drummers", "Jamaican culture festival",
                 "Bob Marley Museum", "Jamaica Art Walk Kingston"],
                r"reggae|music|rasta|culture|art|mural|dance|carnival|drum|festival|marley|band|street|craft", True),
    "couple": (["Black couple Jamaica beach", "couple Jamaica vacation", "interracial couple Caribbean beach", "couple Jamaica waterfall", "romantic Jamaica sunset couple", "couple Jamaica Negril"],
               r"couple|romantic|honeymoon|two|together|love", True),
    "family": (["Black family Jamaica beach", "Jamaican family vacation", "Jamaican mother and child", "Black father and daughter beach", "interracial family Caribbean beach", "Jamaican grandmother with grandchildren", "single mom and son Caribbean beach", "Black family river Jamaica"],
               r"family|kids|children|child|parents|together|group", True),
    "group": (["friends Jamaica beach", "group of friends Jamaica", "friends Jamaica waterfall", "Jamaica friends road trip", "Jamaica group vacation party"],
              r"friends|group|together|party|people|crowd|team", True),
    "solo": (["solo traveler Jamaica", "woman traveler Jamaica", "man Jamaica beach", "Jamaica traveler hiking", "Jamaica beach walk"],
             r"solo|traveler|traveller|alone|hiker|woman|man|walk|tourist|person", True),
}
PEOPLE = ["couple", "family", "group", "solo"]
GENERIC_BOOKING = ["road", "couple", "group", "family", "river", "culture", "food"]

def attractions_for(place):
    p = (place or "").lower()
    for k, v in ATTRACTIONS.items():
        if k in p or p in k:
            return k, v
    return None, []

def attraction_words(city):
    """Words that count as 'this place' in a photo description: the city and each attraction's own name."""
    out = {city}
    for q in ATTRACTIONS.get(city, []):
        w = re.sub(r"\b(jamaica|kingston|town|view|beach|coffee|farm|hills|rafting|safari|river|sunset|cliffs|waterfront)\b", "", q.lower()).strip()
        if len(w) > 3:
            out.add(w)
    return sorted(out)


# ---- time of year: a photo of an event is only used when that event is near (Carnival is in April, so no Carnival photos in November)
SEASONAL = [   # (words in the photo's name/description, months it may be used)
    (re.compile(r"carnival|j'?ouvert|bacchanal|\bmas\b|masquerade|soca", re.I), {3, 4}),
    (re.compile(r"christmas|santa|xmas|grand market|jonkanoo|john canoe", re.I), {11, 12}),
    (re.compile(r"easter|bun and cheese festival", re.I), {3, 4}),
    (re.compile(r"independence|emancipation day|heroes day", re.I), {7, 8, 10}),
    (re.compile(r"reggae sumfest|sumfest", re.I), {7, 8}),
    (re.compile(r"reggae marathon", re.I), {11, 12}),
    (re.compile(r"jamaica cup", re.I), {11}), (re.compile(r"fashion week", re.I), {11}),
    (re.compile(r"spring break|summer", re.I), {3, 4, 5, 6, 7, 8}),
]
def out_of_season(text, month):
    t = text or ""
    return any(rx.search(t) and month not in months for rx, months in SEASONAL)

# ---- things that make a photo wrong for a car-rental brand even when the place matches
JUNK = re.compile(r"polic|\bmask|covid|protest|riot|soldier|military|army|\bgun|weapon|funeral|coffin|hospital|accident|crash|arrest|prison|"
                  r"illustrat|drawing|painting|painted|engraving|lithograph|oil on|watercolo|sketch|poster|postcard|stamp|coin|banknote|"
                  r"portrait of|\bbust\b|statue|\bmap\b|diagram|chart|flag of|coat of arms|logo|screenshot|\bmeme\b|"
                  r"railroad|railway|rail yard|rail tracks|train station|subway|\bmetro\b|locomotive|jamaica station|jamaica avenue|jamaica plain|queens|new york|\bnyc\b|long island|lirr|brooklyn|manhattan|boston|"
                  r"histor|vintage|archiv|antique|sepia|black and white|black & white|monochrome|b&w|colonial|slave|plantation ruins|\b(?:18|19)\d\d\b|\b20[01]\d\b", re.I)

EVENT_THEMES = [(re.compile(r"fashion", re.I), "fashion"), (re.compile(r"tennis", re.I), "tennis")]
def event_theme(*texts):
    t = " ".join(texts)
    for rx, th in EVENT_THEMES:
        if rx.search(t):
            return th


# What a slide talks about -> the photo to search for, so the picture matches the words (coconut water -> coconut vendor, grandma -> grandmother with grandkids).
SLIDE_TOPICS = [
    (r"coconut", ["coconut water vendor Jamaica", "coconut tree Jamaica beach"]),
    (r"\bjerk\b|pimento", ["jerk chicken pit Jamaica", "jerk pork Boston Bay"]),
    (r"patt(y|ies)|coco bread", ["Jamaican beef patty", "Jamaican patty coco bread"]),
    (r"\bfish\b|seafood|lobster", ["fried fish Jamaica beach", "Jamaica seafood plate"]),
    (r"coffee", ["Blue Mountain coffee Jamaica", "coffee farm Jamaica"]),
    (r"ackee|breakfast|rice and peas|sorrel|food|eat|dinner|lunch|cook", ["Jamaican food plate", "Jamaican family dinner"]),
    (r"grandma|grandmother|granny", ["Jamaican grandmother with grandchildren", "grandmother hugging grandchild"]),
    (r"single (mom|mum|mother|dad|father)", ["single mother and child beach", "Black father and son beach"]),
    (r"famil|kids|children|grandkids|cousins|reunion|pickney|graduat", ["Black family Jamaica beach", "Jamaican mother and child", "Black father and daughter beach", "interracial family Caribbean beach"]),
    (r"honeymoon|couple|wedding|romantic|two of you|anniversary", ["Black couple Jamaica beach", "couple Jamaica sunset", "interracial couple Caribbean beach"]),
    (r"friends|girls|crew|birthday|party", ["friends Jamaica beach", "group of friends Jamaica"]),
    (r"waterfall|\bfalls\b|blue hole|swim", ["waterfall Jamaica swimming", "Dunn's River Falls climbing"]),
    (r"river|raft|safari|mangrove|crocodile", ["river rafting Jamaica", "Black River Jamaica boat"]),
    (r"sunset|cliff", ["Negril cliffs sunset", "Jamaica sunset beach"]),
    (r"beach|sand|\bsea\b|ocean|seven mile", ["Jamaica beach people", "Seven Mile Beach Negril"]),
    (r"mountain|hike|holywell|peak|sunrise|mist", ["Blue Mountains Jamaica", "Blue Mountains sunrise"]),
    (r"reggae|music|fete|dancehall|boxing day", ["reggae music Jamaica", "Jamaica street party"]),
    (r"market|vendor|shop|gift|christmas", ["Jamaica market fruit vendor", "Jamaica Christmas market"]),
    (r"airport|\blanded\b|flight", ["Montego Bay Jamaica airport arrival", "travelers airport Caribbean"]),
    (r"cruise|ship|port", ["cruise ship Ocho Rios Jamaica", "Ocho Rios Jamaica bay"]),
    (r"road trip|windows down|bamboo|coastal road|scenic", ["Jamaica coastal road drive", "Bamboo Avenue Jamaica"]),
]

def slide_queries(text):
    """Photo searches that match what a slide says, best match first. Empty when nothing specific is mentioned."""
    t = (text or "").lower()
    return [q for rx, qs in SLIDE_TOPICS if re.search(rx, t) for q in qs]
