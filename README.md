# Vigie — dispositif de veille sectorielle

Une base de code, **un répertoire de configuration par client**. Le client actuel est
`config/` (Ziléa). Reproduire pour un autre cluster = dupliquer `config/`, remplacer
les quatre fichiers JSON, changer `VIGIE_CONFIG`. Aucune ligne de code à toucher.

---

## Ce que ça fait

Chaque lundi à 6h AST, GitHub Actions enchaîne :

1. **Collecte** — 26 flux RSS, bridges Google News, 46 chaînes YouTube, catalogue Viator, compteurs de destination
2. **Écriture** — nouveaux items dans `data/corpus.jsonl`, **compteurs horodatés** dans `data/snapshots.jsonl`
3. **Routage éditorial** — avant tout appel au modèle
4. **Résumé** — un article à la fois, trois phrases, aucune inférence inter-articles
5. **Contrôle de santé** — sources interrogées, réponses, échecs, points à arbitrer
6. **Rendu** — le radar HTML est recalculé depuis le JSON, jamais édité à la main
7. **Publication** — gh-pages + envoi SMTP du digest

Les alertes (cyclone, sargasses, sécheresse) tournent séparément, tous les jours.

---

## La décision d'architecture qui porte tout le reste

**Chaque run écrit un relevé horodaté de tous les compteurs.**

Aucune API concernée ne fournit d'historique : ni Instagram, ni YouTube, ni Viator,
ni Tripadvisor. Un compteur non relevé est perdu.

Conséquence : **la valeur est dans les écarts, et les écarts n'existent que si on a
commencé à stocker tôt.** Semaine 1, le radar montre un état. Semaine 8, il montre un
mouvement — un opérateur qui décroche, un prix qui grimpe avant la haute saison, une
chaîne qui se réveille.

`data/` est committé à chaque run. C'est volontaire : le dépôt *est* l'historique.

---

## Installation

```
git clone <depot> && cd vigie
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/smoke_test.py
```

Le test de fumée tourne sans réseau ni clé API. Il vérifie le routage éditorial,
le classement, le calcul d'écart, la génération du digest et le rendu du radar.

### Clés

| Variable | Obligatoire | Obtention |
|---|---|---|
| `ANTHROPIC_API_KEY` | pour les résumés | console.anthropic.com — quelques centimes par run |
| `YOUTUBE_API_KEY` | non | console.cloud.google.com, API YouTube Data v3. Sans elle, les titres et dates sont collectés par flux public ; seules les vues manquent |
| `VIATOR_API_KEY` | non | Compte Viator → Tools → Affiliate API. **Gratuit, self-service** |
| `SMTP_*` | pour l'envoi | Brevo, Mailjet ou équivalent |

### Prérequis DNS — bloquant

`SPF`, `DKIM` et `DMARC` sur le domaine d'envoi. Sans eux, l'envoi hebdomadaire vers
88 destinataires part en indésirable et le dispositif passe pour cassé alors que la
collecte fonctionne. **À régler avant le premier envoi, pas après.**

---

## Répétition générale — sans DNS ni SMTP

Le dispositif tourne de bout en bout sans avoir rien débloqué. Trois commandes.

```
python scripts/adopt_keys.py ~/Documents/Bystronic_Radar/.env
python scripts/seed.py
VIGIE_SIMULATE_DELIVERY=1 SMTP_FROM=vigie@zilea-martinique.com python run.py --send
```

**`adopt_keys.py`** reprend les clés d'un `.env` existant sans jamais afficher une
valeur. Il ne copie que les huit variables attendues, ignore le reste, n'écrase
aucune valeur déjà renseignée, et pose le fichier en `chmod 600`.

**`seed.py`** amorce le corpus avec la collecte déjà réalisée : 137 articles,
110 vidéos, 71 activités, 12 compteurs de destination. Sans cet amorçage, le
premier run affiche un radar vide et aucun écart — les séries ne commencent qu'au
deuxième relevé. Avec, le dispositif démarre avec six mois d'historique et le
premier écart tombe dès la semaine suivante.

**`VIGIE_SIMULATE_DELIVERY=1`** construit le message, le contrôle, l'écrit en
`.eml` dans `out/`, et traite les enregistrements DNS manquants comme publiés.
Aucun octet ne sort.

### Le préflight de délivrabilité

```
python scripts/dns_preflight.py
```

Il interroge réellement le DNS. En mode réel, l'envoi est **refusé** tant que SPF,
DKIM et DMARC ne répondent pas — c'est volontaire : un envoi hebdomadaire vers 88
destinataires sans ces trois enregistrements part en indésirable, et le dispositif
passe pour cassé alors que la collecte fonctionne. Mieux vaut ne pas envoyer que
d'envoyer dans le vide.

En mode simulé, il affiche les enregistrements exacts à publier et laisse passer :

```
  [-- ] SPF   zilea-martinique.com
          à publier : v=spf1 include:<votre-routeur-smtp> -all
  [-- ] DKIM  vigie._domainkey.zilea-martinique.com
          à publier : v=DKIM1; k=rsa; p=<clé publique fournie par le routeur>
  [-- ] DMARC _dmarc.zilea-martinique.com
          à publier : v=DMARC1; p=quarantine; rua=mailto:dmarc@...; adkim=s; aspf=s
```

Passer en réel ne demande qu'une chose : publier les trois enregistrements et
retirer `VIGIE_SIMULATE_DELIVERY`. Aucune ligne de code ne change.

### Ce que le `.eml` permet de vérifier

Le fichier s'ouvre dans n'importe quel client de messagerie. Il porte déjà
`List-Unsubscribe` en un clic (RFC 8058), `List-Id`, `Auto-Submitted:
auto-generated`, et les deux alternatives HTML et texte brut. C'est ce qui sera
envoyé, à l'octet près.


---

## Exploitation

```
python run.py --cadence weekly            run complet
python run.py --cadence weekly --dry-run  sans appel au modèle
python run.py --cadence daily             alertes seulement
python run.py --render-only               régénère le radar depuis le corpus
python run.py --preflight                 contrôle DNS seulement
python run.py --send                      envoie le digest (ou écrit un .eml si simulation)
```

### Secrets GitHub à créer

`ANTHROPIC_API_KEY`, `YOUTUBE_API_KEY`, `VIATOR_API_KEY`, `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.

Activer Pages sur le dépôt, source « GitHub Actions ».

---

## Configuration

| Fichier | Contenu |
|---|---|
| `config/client.json` | Identité, charte graphique, cadence, seuils |
| `config/sources.json` | 26 flux, requêtes Google News, pages sans flux, alertes, calendrier institutionnel, sources bloquées |
| `config/entities.json` | Watchlist presse, 46 chaînes YouTube, 45 comptes Instagram, marketplaces, destinations de benchmark |
| `config/editorial.json` | Routage président, exclusions, contraintes de résumé, mentions légales |

Tout est éditable sans savoir coder.

### Deux pièges inscrits dans la config

**Google News.** Ne jamais construire les requêtes sur `site:domaine-adhérent`. Sur un
dispositif comparable, 97 % du corpus s'est révélé être du contenu publié par les
entreprises elles-mêmes : le classement mesurait l'indexation Google, pas la couverture
presse. La requête correcte porte sur la mention de marque en excluant le domaine propre.

**Marketplaces.** Le prix et la devise varient selon la géolocalisation. `LOCALE` et
`CURRENCY` sont fixés dans `collectors/offers.py` et ne doivent jamais changer, sinon
la série devient incomparable.

---

## Règles éditoriales

Le modèle ne peut presque rien inventer, par construction et non par consigne.

**Titre, source, date et URL sont recopiés.** Ils ne passent jamais par un modèle. Le
champ `verbatim` de chaque item liste ces champs.

**Un résumé, un article.** Trois phrases maximum, aucune inférence inter-articles,
aucun chiffre absent du texte fourni. Si le texte est trop court, le champ reste vide
et le radar affiche « source sans descriptif » plutôt que de combler.

**Le routage précède la rédaction.** Un item capté par `president_only_patterns` n'est
jamais résumé — il ne peut donc pas fuiter par une reformulation.

**Plancher de publication.** Sous `min_items`, pas d'envoi. Le corpus donne la mesure :
août 2026 tombe à six items pour tout le secteur.

---

## Cadences

| Couche | Cadence | Pourquoi |
|---|---|---|
| Alertes | quotidienne | Un bulletin d'échouement à 4 jours n'a aucune valeur relevé une semaine plus tard |
| Presse, vidéos, offre | hebdomadaire | 3 à 4 items de presse par semaine ; 2 à 3 vidéos par mois pour tout le cluster |
| Santé, inventaires | mensuelle | Une chaîne renommée se détecte sans urgence |
| Chiffres institutionnels | trimestrielle, sur calendrier | INSEE, IEDOM et CEROM publient à dates connues, ce ne sont pas des flux |

---

## Ce qui casse, et comment on le voit

Le pied de page du digest porte le compteur de santé. `out/a_arbitrer.json` liste :

- les sources muettes deux runs de suite — candidates au retrait
- **les codes produit disparus du catalogue** — ce n'est pas une panne, c'est le signal
  qu'un opérateur a cessé d'être distribué

---

## Reproduire pour un autre client

```
cp -r config config-nouveauclient
# éditer les 4 JSON
VIGIE_CONFIG=config-nouveauclient VIGIE_DATA=data-nouveauclient python run.py --cadence weekly
```

Le code ne contient aucune référence en dur à Ziléa ni à la Martinique. Les couleurs,
la typographie, le nom, les sources, les entités et les règles éditoriales viennent
tous de la configuration.

---

## Limites assumées

- **Les Shorts YouTube ne sont pas couverts.** L'onglet Vidéos les exclut ; neuf chaînes en exposent un onglet distinct.
- **Martinique la 1ère est inaccessible.** robots.txt refuse tout le domaine, flux compris.
- **Pas de capacité aérienne programmée.** Aucune source gratuite de sièges programmés. OAG et Cirium vendent sur devis.
- **Instagram n'est pas branché.** Business Discovery exige une app Meta, une Page Facebook liée et une revue d'application. Le dispositif n'en porte que l'inventaire des comptes.
- **Facebook est hors périmètre**, et c'est un choix. Le scraping de pages publiques est défendable juridiquement mais place la responsabilité RGPD sur l'opérateur du dispositif.
