"""Taxonomie partagee par la presse et les videos.

Deux axes independants, et c'est le point : le theme dit DE QUOI il s'agit,
le territoire dit OU. Melanger les deux etait l'erreur d'origine — une nocturne
au Parc Asterix est correctement classee en frequentation, elle n'a simplement
rien a faire dans un radar martiniquais. Un seul axe ne pouvait pas exprimer ca.

Aucun appel au modele ici. Des regles lisibles, modifiables par le cluster.
"""
import re

# --- Axe 1 : le theme, en deux familles ------------------------------------
# Tout article porte une etiquette. La famille dit s'il releve du secteur ou
# non ; le theme dit de quoi il parle. Sans la famille, un fil de presse
# generaliste remplit le radar d'articles sans nom — la moitie du corpus — et
# on ne sait plus si c'est l'outil qui echoue ou la source qui deborde.

TOURISME = ["FREQ", "AIR", "CROIS", "ENV", "GOUV", "DISTRI", "OFFRE"]
HORS = ["MOB", "SOC", "ECO"]
THEMES = TOURISME + HORS + ["NC"]

FAMILY = {t: "tourisme" for t in TOURISME}
FAMILY.update({t: "hors" for t in HORS})
FAMILY["NC"] = "nc"

FAMILY_LABELS = {"tourisme": "Secteur touristique",
                 "hors": "Hors secteur",
                 "nc": "Sans \u00e9tiquette"}

LABELS = {
    "FREQ": "Fr\u00e9quentation & \u00e9conomie du secteur",
    "AIR": "A\u00e9rien",
    "CROIS": "Croisi\u00e8re & nautisme",
    "ENV": "Sargasses, eau & climat",
    "GOUV": "Institutions & politiques",
    "DISTRI": "Distribution & commercialisation",
    "OFFRE": "Offre & vie de la destination",
    "MOB": "Transports & mobilit\u00e9",
    "SOC": "Soci\u00e9t\u00e9 & vie locale",
    "ECO": "\u00c9conomie hors tourisme",
    "NC": "Sans \u00e9tiquette",
}

# L'ordre compte : la premiere regle qui mord l'emporte. Les themes du secteur
# passent avant ceux hors secteur, et les plus specifiques avant les plus larges.
RULES = [
    ("CROIS", [
        "croisi", "escale", "paquebot", "\\bmsc\\b", "grand port", "t\u00eate de ligne",
        "yole", "voilier", "nautisme", "marina", "plaisance", "catamaran", "r\u00e9gate",
        "cruise", "cruise line", "port call", "\\byacht", "sailing", "royal caribbean",
        "norwegian cruise", "\\bcarnival\\b", "shore excursion",
        "navigation|naviguer|\\bskipper\\b|charter nautique|\\bvoile\\b|\\bponton\\b",
    ]),
    ("AIR", [
        "a\u00e9rien", "a\u00e9roport", "air[- ]cara\u00efbes|air[- ]caraibes", "air[- ]france",
        "corsair", "air[- ]transat", "air[- ]antilles", "air[- ]belgium|air[- ]century", "aim\u00e9 c\u00e9saire", "\\bsamac\\b",
        "liaison", "desserte", "ligne directe", "compagnie a\u00e9rienne",
        "low cost", "si\u00e8ges offerts",
        "air canada|american airlines|delta air|jetblue|westjet|united airlines|iberia|klm|lufthansa",
        "\\bboeing\\b|\\bairbus\\b|constructeur a\u00e9ronautique", "\\bcabin crew\\b|\\bpilots?\\b", "vol direct|vols? vers|vols? au d\u00e9part|nombre de vols",
        "\\bairlines?\\b", "\\bairways\\b", "\\bairport\\b", "nonstop|non-stop",
        "\\bflights?\\b", "seat capacity", "air service", "\\biata\\b",
        "\\baviation\\b", "\\bavions?\\b", "escale technique", "fret a\u00e9rien",
        "air[- ](europa|caraibes|cara\u00efbes|canada|antilles|century|belgium|s\u00e9n\u00e9gal|austral)",
        "\\bhub a\u00e9rien\\b|\\bcorrespondances?\\b|\\bslots?\\b",
    ]),
    ("ENV", [
        "sargasse", "s\u00e9cheresse", "cyclon", "vigilance", "baignade",
        "m\u00e9t\u00e9o", "\u00e9chouement", "chlord\u00e9cone", "\u00e9rosion", "submersion",
        "qualit\u00e9 de l'eau", "coupure d'eau", "tours? d'eau", "\u00e9pisode de pollution",
        "temp\u00e9rature|canicule|\\bchaleur\\b|normales de saison", "\\bseisme\\b|\\bs\u00e9isme\\b",
        "sargassum", "drought", "hurricane", "tropical storm", "water quality",
        "coral|r\u00e9cif", "climate change",
        "onde tropicale|vents violents|\\borages?\\b|intemp\u00e9ries|\\bhoule\\b",
        "biodiversit\u00e9|\\besp\u00e8ces\\b|naturaliste|\\bfaune\\b|\\bflore\\b|mangrove",
        "zones? \u00e0 risques|risques naturels|pr\u00e9vention des risques|\\bs\u00e9ismes?\\b",
    ]),
    ("DISTRI", [
        "agent de voyages", "tour-op", "tour op\u00e9rateur", "eductour", "\u00e9ductour",
        "exotismes", "brochure", "\\biftm\\b", "top r\u00e9sa", "top resa",
        "salon du tourisme", "world travel market", "workshop", "voyagiste",
        "r\u00e9ceptif", "autocariste", "\\bgds\\b", "distribution",
        "tour operator", "travel agent|travel advisor", "trade show", "\\bota\\b",
        "booking platform", "familiarization trip|\\bfam trip\\b",
    ]),
    ("GOUV", [
        "\\bcmt\\b", "comit\u00e9 martiniquais", "\\bctm\\b", "pr\u00e9fecture",
        "collectivit\u00e9 territoriale", "\\bs\u00e9nat\\b", "\\bfedom\\b",
        "octroi de mer", "zil\u00e9a", "\\bumih\\b", "\\bmedef\\b",
        "chambre de commerce", "plan d'urgence", "subvention", "d\u00e9lib\u00e9ration",
        "assembl\u00e9e de martinique",
        "minist(re|\u00e8re)s? (du|de la|des) (tourisme|outre-mer|transports|\u00e9conomie)",
        "union europ\u00e9enne|commission europ\u00e9enne|r\u00e9gions ultrap\u00e9riph",
        "tourism board|tourist board|\\bdmo\\b", "ministry of tourism",
        "tourism authority|tourism ministry",
    ]),
    ("OFFRE", [
        "h\u00f4tel", "h\u00e9bergement", "g\u00eete", "villa", "r\u00e9sidence de tourisme",
        "restaurant", "gastronomie",
        "chefs? (cuisinier|\u00e9toil\u00e9|de cuisine|de rang)|\\bchefs\\b",
        "\\brhum\\b", "distillerie", "habitation", "jardin", "mus\u00e9e", "exposition",
        "festival", "carnaval", "randonn\u00e9e", "plong\u00e9e", "excursion", "loisir",
        "spa\\b", "plage", "location de voiture", "\u00e9v\u00e9nement", "concert",
        "patrimoine", "que faire|choses \u00e0 faire|\\btop \\d+\\b|d\u00e9couverte de",
        "\\banse\\b|\\bbaie\\b|fonds blancs|\\bmorne\\b|\\b\u00eelets?\\b|cascade|\\bpiton\\b|\\bcap\\b",
        "live acoustique|\\bs\u00e9sy|\\bmizik\\b|\\bb\u00e8l\u00e8\\b|\\bgwo ka\\b|\\bchant\u00e9\\b",
        "visite guid\u00e9e|\\bbalade\\b|week-end|\u00e9vasion|\\bcircuit\\b",
        "location (de )?voitures?|voiture de location|louer une voiture|\\bautolocation\\b",
        "\\bhotels?\\b", "\\bresorts?\\b", "all-inclusive", "\\bbeach\\b",
        "guesthouse|boutique hotel", "\\brum\\b|distillery", "\\bmuseum\\b",
        "\\bdiving\\b|\\bsnorkel", "rainforest|\\breef",
    ]),
    ("FREQ", [
        "fr\u00e9quentation", "nuit\u00e9e", "arriv\u00e9es", "taux d'occupation", "visiteur",
        "s\u00e9jour", "chiffre d'affaires", "saison touristique", "bilan de saison",
        "\\binsee\\b", "\\biedom\\b", "recettes", "d\u00e9penses des touristes",
        "croissance", "d\u00e9faillance", "march\u00e9 \u00e9metteur",
        # le vocabulaire generique du secteur atterrit ici : un article qui parle
        # de tourisme sans rien de plus precis reste un article de tourisme
        "tourisme|touristique|touriste", "\\btourism\\b", "\\btravel\\b|traveller|traveler",
        "\\bvisitors?\\b", "\\barrivals\\b", "occupancy", "\\bhospitality\\b",
        "voyage d'affaires|business travel", "\\bvoyagistes?\\b|\\bvoyages?\\b",
    ]),
    # --- hors secteur : etiqueter plutot que laisser vide ---
    ("MOB", [
        "\\bbus\\b", "\\btcsp\\b", "transport (public|collectif|scolaire)",
        "circulation", "embouteillage", "\\bferry\\b", "navette maritime",
        "\\btaxis?\\b", "\\bsncf\\b", "\\btrains?\\b", "r\u00e9seau routier",
        "travaux de voirie", "mobilit\u00e9",
        "\\broads?\\b|\\btraffic\\b|public transport|\\bbuses\\b",
        "transports? (public|collectif|scolaire)s?|\\bsudlib\\b|martinique transport",
        "chauffeurs?|conducteurs?|accident de (car|bus|la route)|\\bcars?coop\\b",
    ]),
    ("SOC", [
        "justice|tribunal correctionnel|proc\u00e8s|\\bjug\u00e9\\b", "gendarmerie|\\bpolice\\b",
        "cambriolage|meurtre|homicide|agression|violence", "\\bh\u00f4pital\\b|\\bchu\\b|sant\u00e9 publique",
        "\\b\u00e9cole\\b|coll\u00e8ge|lyc\u00e9e|universit\u00e9|rentr\u00e9e scolaire",
        "\\bgr\u00e8ve\\b|syndicat|manifestation", "logement social|\\bhlm\\b",
        "\\bfootball\\b|cyclisme|\\bcycliste\\b|tour cycliste|\\bv\u00e9lo\\b|championnat|\\bmiss\\b|\\bmister\\b",
        "\\bgossip\\b|\\bpeople\\b|t\u00e9l\u00e9r\u00e9alit\u00e9|\\bbuzz\\b",
        "d\u00e9c\u00e8s|obs\u00e8ques|hommage", "\\breggae\\b|\\bzouk\\b", "mortalit\u00e9|esp\u00e9rance de vie|\u00e9pid\u00e9mie",
        "journal t\u00e9l\u00e9vis\u00e9|\\bJT du\\b|cyberattaque|fait divers",
        "\\bcourt\\b|\\bfined\\b|\\bsentenced\\b|\\bpolice\\b|\\bcocaine\\b|\\barrested\\b",
        "\\bhospital\\b|\\bschools?\\b|\\bstudents?\\b|\\bhealth\\b",
        "\\bcricket\\b|\\bfootball\\b|\\bathletes?\\b|\\bchampionship\\b",
        "\\belections?\\b|\\bparliament\\b|\\bminister\\b|\\bgovernment\\b|\\bvisa\\b",
        "letter to the editor|\\bobituary\\b|\\bfuneral\\b",
        "gouvernement|assembl\u00e9e nationale|\u00e9lections?|remaniement|\\bpr\u00e9fet\\b",
        "rectorat|enseignants?|\u00e9l\u00e8ves|parents d'\u00e9l\u00e8ves|\\bcrous\\b",
        "\\behpad\\b|maison de retraite|\\baide sociale\\b|\\bcaf\\b",
        "\\bgendarmes?\\b|disparition inqui\u00e9tante|\\brecherches\\b|\\bsecours\\b",
        "championne?s?|motocross|\\bathl\u00e9tisme\\b|\\bbasket\\b|\\bvoile sportive\\b",
        "\\bunesco\\b|fellowship|\\bscholarship\\b|\\brecherche scientifique\\b",
    ]),
    ("ECO", [
        "entreprise|\\bpme\\b|patronat", "\\bemplois?\\b|ch\u00f4mage|recrutement",
        "\\bbtp\\b|chantier|construction", "agricult|\u00e9levage|\\bp\u00each",
        "\\bbanque\\b|financement|investissement", "vie ch\u00e8re|pouvoir d'achat|inflation",
        "\\b\u00e9nergie\\b|\u00e9lectricit\u00e9|\\bedf\\b", "num\u00e9rique|t\u00e9l\u00e9com|\\bwifi\\b",
        "march\u00e9 public|appel d'offres", "\\bexports?\\b|importation",
        "\u00e9conomie|\u00e9conomique|croissance du pib|r\u00e9cession",
        "\\beconomy\\b|\\bbusiness\\b|\\btrade\\b|\\bexports?\\b|\\bjobs?\\b|\\bworkers?\\b",
        "main-d'\u0153uvre|france travail|besoins en recrutement|\\bp\u00f4le emploi\\b",
        "\\bgouvernance\\b|\\bdirecteur g\u00e9n\u00e9ral\\b|\\bnomination\\b|\\bconseil d'administration\\b",
    ]),
]

_RULES = [(t, [re.compile(p, re.I) for p in pats]) for t, pats in RULES]


# --- Axe 2 : le territoire -------------------------------------------------
TERRITORIES = ["MQ", "CARAIBE", "MONDE"]
TERR_LABELS = {"MQ": "Martinique", "CARAIBE": "Cara\u00efbe", "MONDE": "Secteur monde"}

_MQ = [re.compile(p, re.I) for p in [
    "martiniq",
    "fort-de-france|schoelcher|le lamentin|sainte-anne|sainte-luce|le fran\u00e7ois"
    "|le robert|trois-\u00celets|trois-ilets|saint-pierre|le diamant|le marin|le carbet"
    "|le pr\u00eacheur|sainte-marie|la trinit\u00e9|les anses-d'arlet|le vauclin",
    "aim\u00e9 c\u00e9saire|montagne pel\u00e9e|rocher du diamant|baie des flamands|\\bfdf\\b",
]]
_CARAIBE = [re.compile(p, re.I) for p in [
    "guadeloupe|sainte-lucie|saint-lucia|barbade|barbados|la dominique|\\bdominica\\b"
    "|cuba|jama\u00efque|jamaica|dominicaine|saint-martin|sint maarten|antigua"
    "|\u00celes vierges|porto rico|puerto rico|aruba|cura\u00e7ao|bahamas|trinidad"
    "|guyane|antilles|cara\u00efbe|caribbean|\\bcaraibes?\\b",
]]


def territory(blob, source="", local_sources=()):
    """MQ l'emporte sur CARAIBE, qui l'emporte sur MONDE.

    Un article qui parle de la Martinique ET de la Guadeloupe est un article
    martiniquais : c'est l'angle du cluster, pas celui du redacteur.
    """
    if source and source.strip().lower() in local_sources:
        return "MQ"
    for rx in _MQ:
        if rx.search(blob):
            return "MQ"
    for rx in _CARAIBE:
        if rx.search(blob):
            return "CARAIBE"
    return "MONDE"


def theme(blob):
    for t, rxs in _RULES:
        for rx in rxs:
            if rx.search(blob):
                return t, "regles"
    return "NC", "defaut"
