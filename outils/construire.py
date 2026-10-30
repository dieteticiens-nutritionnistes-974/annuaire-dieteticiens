"""Construit index.html à partir de l'export CSV du formulaire « Annuaire ».

Usage :
    python3 outils/construire.py chemin/vers/export.csv

Produit :
    index.html             la page publiée (données et photos intégrées)
    rapport-anomalies.md   ce qu'il faut vérifier avant de publier (non versionné)

Les corrections manuelles (noms, communes, liens, personnes à exclure)
se font dans corrections.json, jamais dans le CSV ni dans index.html.
"""
import base64, csv, io, json, re, sys, unicodedata, urllib.request
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Il manque la bibliothèque Pillow : lancez  python3 -m pip install Pillow")

RACINE = Path(__file__).resolve().parent.parent
CACHE = RACINE / "cache" / "photos"

CATEGORIES = ["Métabolisme et maladies chroniques", "Troubles digestifs", "Comportement alimentaire",
              "Santé de la femme", "Étapes et situations de vie", "Autres domaines"]
APPROCHES = {"approche educative": "Éducative", "approche comportementale": "Comportementale",
             "approche motivationnelle": "Motivationnelle / coaching", "approche globale": "Globale"}
APPROCHES_DESC = {
    "Éducative": "Apports, équilibre et repères alimentaires",
    "Comportementale": "Habitudes, pensées, émotions et sensations alimentaires",
    "Motivationnelle / coaching": "Objectifs et changement progressif des habitudes",
    "Globale": "Mode de vie et facteurs qui influencent l'alimentation",
}
MODALITES = {"presentiel": "Cabinet", "teleconsultation": "Visio", "domicile": "Domicile"}
# Colonnes du formulaire, repérées par un extrait de leur intitulé (sans accents, en minuscules)
COLONNES = {
    "horodateur": "horodateur", "nom": "nom et prenom", "structure": "structure", "rpps": "rpps",
    "communes": "commune", "modalites": "modalites", "publics": "publics", "approches": "approche",
    "outils": "methodes et outils", "prestations": "autres prestations", "formations": "formations",
    "photo": "photo", "tel": "telephone", "email": "email", "site": "site internet",
    "facebook": "facebook", "instagram": "instagram", "linkedin": "linkedin", "rdv": "rdv",
    "autre": "autre lien", "pitch": "votre presentation",
}


def cle(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", cle(s)).strip("-")


corr = json.load(open(RACINE / "corrections.json", encoding="utf-8"))
anomalies = []


def corrige(s):
    for a, b in corr.get("fautes", {}).items():
        s = s.replace(a, b)
    return s.strip()


def liste(s):
    """Découpe une réponse à choix multiples, sans couper sur les virgules entre parenthèses."""
    out, buf, prof = [], "", 0
    for c in s:
        prof += (c == "(") - (c == ")")
        if c == "," and prof == 0:
            out.append(buf); buf = ""
        else:
            buf += c
    out.append(buf)
    return [corrige(x) for x in out if x.strip()]


def nom_prenom(brut):
    if brut in corr.get("noms", {}):
        return tuple(corr["noms"][brut])
    mots = brut.split()
    maj = [m for m in mots if m.isupper() and len(m) > 1]
    if maj and len(maj) < len(mots):
        nom = " ".join(maj)
        prenom = " ".join(m for m in mots if m not in maj)
    elif len(mots) >= 2:
        nom, prenom = mots[0], " ".join(mots[1:])  # « NOM Prénom » par défaut
    else:
        anomalies.append(f"« {brut} » : prénom manquant (ajouter une entrée dans corrections.json > noms)")
        return ("", brut.title())
    titre = lambda s: "-".join(p.capitalize() for p in s.lower().split("-"))
    return (" ".join(titre(m) for m in prenom.split()), " ".join(titre(m) for m in nom.split()))


GEO = json.load(open(RACINE / "src/communes.json", encoding="utf-8"))
COMMUNES = {cle(f["properties"]["nom"]).replace("-", " "): f["properties"]["nom"] for f in GEO["features"]}


def commune(brut, qui):
    k = cle(corr.get("communes", {}).get(brut, brut)).replace("-", " ").replace("phillippe", "philippe")
    k = re.sub(r"\s+", " ", k)
    if k in COMMUNES:
        return COMMUNES[k]
    anomalies.append(f"{qui} : commune non reconnue « {brut} » (ajouter un alias dans corrections.json > communes)")
    return None


def tel(s):
    d = re.sub(r"\D", "", s)
    if d.startswith("262") and len(d) == 12:
        d = "0" + d[3:]
    return " ".join([d[:4]] + [d[i:i + 2] for i in range(4, 10, 2)]) if len(d) == 10 else s.strip()


def url(s):
    s = s.strip()
    if not s or " " in s or "." not in s:
        return ""
    return s if s.lower().startswith("http") else "https://" + s.lower()


def type_lien(u):
    h = u.lower()
    if "linkedin.com/in/" in h: return "linkedin"
    if "linkedin" in h: return None
    if "instagram.com" in h: return "instagram"
    if "facebook.com" in h: return "facebook"
    if any(k in h for k in ("doctolib", "calendly", "/reservation", "monsuividiet", "rdv")): return "rdv"
    return "site"


def photo(lien, qui):
    m = re.search(r"id=([\w-]+)", lien or "")
    if not m:
        return ""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{m.group(1)}.img"
    if not f.exists():
        try:
            req = urllib.request.Request(f"https://drive.google.com/thumbnail?id={m.group(1)}&sz=w600",
                                         headers={"User-Agent": "Mozilla/5.0"})
            f.write_bytes(urllib.request.urlopen(req, timeout=30).read())
        except Exception as e:
            anomalies.append(f"{qui} : photo impossible à télécharger ({e}). Vérifier que le fichier Drive est partagé « tous les utilisateurs disposant du lien »")
            return ""
    try:
        im = Image.open(f).convert("RGB")
    except Exception:
        f.unlink(missing_ok=True)
        anomalies.append(f"{qui} : la photo Drive n'est pas une image lisible (fichier non partagé publiquement ?)")
        return ""
    w, h = im.size
    c = min(w, h)
    top = int((h - c) * 0.2)  # léger biais vers le haut pour garder le visage
    im = im.crop(((w - c) // 2, top, (w - c) // 2 + c, top + c)).resize((320, 320), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=78, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def construire(chemin_csv):
    lignes = list(csv.reader(open(chemin_csv, encoding="utf-8-sig")))
    entete, rows = lignes[0], [r for r in lignes[1:] if any(x.strip() for x in r)]
    cles = [cle(h) for h in entete]
    col = {}
    for nom, motif in COLONNES.items():
        idx = next((i for i, h in enumerate(cles) if motif in h and i not in col.values()), None)
        if idx is None:
            sys.exit(f"Colonne introuvable dans le CSV : « {motif} ». Le formulaire a changé, adapter COLONNES dans outils/construire.py")
        col[nom] = idx
    col_dom = {}
    for i, h in enumerate(cles):
        m = re.match(r"^(\d)\.", h)
        if m and 1 <= int(m.group(1)) <= len(CATEGORIES):
            col_dom[CATEGORIES[int(m.group(1)) - 1]] = i

    # Une seule fiche par personne : la réponse la plus récente l'emporte
    def date(r):
        try: return datetime.strptime(r[col["horodateur"]].strip(), "%d/%m/%Y %H:%M:%S")
        except ValueError: return datetime.min
    par_personne = {}
    for r in sorted(rows, key=date):
        k = slug(r[col["nom"]])
        if k in par_personne:
            anomalies.append(f"{r[col['nom']].strip()} : plusieurs réponses, seule la plus récente est gardée")
        par_personne[k] = r

    exclus = {slug(x) for x in corr.get("exclure", [])}
    pros = []
    for k, r in par_personne.items():
        brut = r[col["nom"]].strip()
        if k in exclus:
            continue
        prenom, nom = nom_prenom(brut)
        qui = f"{prenom} {nom}".strip()
        v = lambda c: r[c].strip() if c < len(r) else ""

        communes = [c for c in (commune(x, qui) for x in liste(v(col["communes"]))) if c]
        if not communes:
            anomalies.append(f"{qui} : aucune commune reconnue, la fiche n'apparaît pas sur la carte")

        liens, ignores = {}, set(corr.get("liens_ignores", []))
        for champ in ("site", "facebook", "instagram", "linkedin", "rdv", "autre"):
            brut_l = v(col[champ])
            if not brut_l or brut_l in ignores:
                continue
            if champ == "instagram" and re.fullmatch(r"@?[\w.]+", brut_l) and "instagram" not in brut_l:
                u = "https://www.instagram.com/" + brut_l.lstrip("@") + "/"
                anomalies.append(f"{qui} : identifiant Instagram « {brut_l} » converti en lien, à vérifier")
            else:
                u = url(brut_l)
            if not u:
                anomalies.append(f"{qui} : champ {champ} sans lien utilisable (« {brut_l} »), non affiché")
                continue
            t = type_lien(u)
            if t is None:
                anomalies.append(f"{qui} : lien {champ} inutilisable (« {brut_l[:60]} »), non affiché")
                continue
            if champ not in ("site", "autre") and t not in (champ, "site"):
                anomalies.append(f"{qui} : le champ {champ} contient un lien {t}")
            liens.setdefault(t, u)
        if "rdv" in liens and liens.get("site") == liens["rdv"]:
            del liens["site"]

        approches = []
        for a in re.split(r",\s*(?=Approche )", v(col["approches"])):
            for debut, court in APPROCHES.items():
                if cle(a).startswith(debut):
                    approches.append(court)

        rpps = v(col["rpps"])
        p = {
            "id": slug(qui), "prenom": prenom, "nom": nom,
            "structure": corr.get("structures", {}).get(v(col["structure"]), v(col["structure"])),
            "rpps": re.sub(r"(?i)adeli\s*:?", "", rpps).strip(),
            "rppsType": "ADELI" if "adeli" in rpps.lower() else "RPPS",
            "communes": communes,
            "modalites": [m for k2, m in MODALITES.items() if k2 in cle(v(col["modalites"]))],
            "publics": liste(v(col["publics"])),
            "domaines": {c: liste(v(i)) for c, i in col_dom.items() if liste(v(i))},
            "approches": approches,
            "outils": liste(v(col["outils"])),
            "prestations": liste(v(col["prestations"])),
            "formations": [corrige(x.strip(" -")) for x in re.split(r"\n|//", v(col["formations"])) if x.strip(" -")],
            "photo": photo(v(col["photo"]), qui),
            "tel": tel(v(col["tel"])),
            "email": v(col["email"]).lower(),
            "liens": liens,
            "pitch": v(col["pitch"]),
        }
        if p["structure"] == brut:
            p["structure"] = ""
        for champ, val in corr.get("surcharges", {}).get(p["id"], {}).items():
            if champ not in p or champ in ("id", "photo"):
                anomalies.append(f"{qui} : surcharge ignorée, champ inconnu « {champ} »")
            else:
                p[champ] = val
        if not p["photo"]: anomalies.append(f"{qui} : pas de photo (initiales affichées)")
        if not p["pitch"]: anomalies.append(f"{qui} : pas de présentation")
        pros.append(p)

    pros.sort(key=lambda p: cle(p["nom"]))
    data = {"pros": pros, "approchesDesc": APPROCHES_DESC, "categories": CATEGORIES}
    page = (RACINE / "src/gabarit.html").read_text(encoding="utf-8")
    page = page.replace("/*DATA*/", json.dumps(data, ensure_ascii=False)).replace(
        "/*GEO*/", json.dumps(GEO, separators=(",", ":")))
    (RACINE / "index.html").write_text(page, encoding="utf-8")

    rapport = [f"# Rapport de construction : {len(pros)} fiches", "",
               f"Source : {Path(chemin_csv).name}", "",
               "## Fiches publiées", ""] + [f"- {p['prenom']} {p['nom']} ({', '.join(p['communes'])})" for p in pros] + \
              ["", f"## Points à vérifier ({len(anomalies)})", ""] + [f"- {a}" for a in anomalies]
    (RACINE / "rapport-anomalies.md").write_text("\n".join(rapport) + "\n", encoding="utf-8")
    print(f"{len(pros)} fiches, {len(anomalies)} points à vérifier (voir rapport-anomalies.md)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    construire(sys.argv[1])
