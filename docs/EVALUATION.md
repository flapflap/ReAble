# ReAble — évaluation technique

_7 octobre 2026 · basée sur une recherche web et sur un prototype testé avec un vrai set (Live 12.0.1 : 4 × Massive X en AU, Battery 4, Neutron 3 et Ozone 10 en VST3)._

## En bref

| Étape | Faisabilité | Statut |
|---|---|---|
| 1. Scanner un dossier de sets | Facile | ✅ fait dans le prototype |
| 2. Détecter les plugins manquants | Moyen (macOS) | ✅ AU par identifiant exact, VST3 par UID ou par nom. À valider sur le Mac |
| 3. Extraire preset, paramètres, automations | Facile pour la structure Live. Variable pour l'état interne, selon le plugin | ✅ Live : générique · ✅ Massive X (NI) et iZotope : décodés |
| 4. Résumer | Facile | ✅ rapport Markdown + JSON complet |
| 5a. Réécrire vers le **même plugin dans un autre format** (AU→VST3, VST2→VST3) | Probablement faisable pour NI, à prouver | 🔬 hypothèse forte, à tester avec un set de référence |
| 5b. Réécrire vers un **autre plugin** (ex. Massive X → Vital) | Très difficile en automatique | 💡 fiche de recréation, et éventuellement une approximation assistée par l'IA |

**Verdict :** les étapes 1 à 4 sont solides et déjà prototypées. L'étape 5a est le vrai différenciateur. Elle est réaliste pour les plugins qui gardent le même état entre formats, comme le suggèrent les plugins NI, mais il faut le prouver plugin par plugin. L'étape 5b doit rester une aide manuelle.

## 1. Ce qui existe déjà (recherche du 7 octobre 2026)

| Outil | Ce qu'il fait | Ce qu'il ne fait pas |
|---|---|---|
| [abletoolz](https://github.com/elixirbeats/abletoolz), v2.1, août 2026, GPL-3, CLI Python | Scanne les sets et détecte les plugins manquants (AU par identité de composant, VST3 par bundle). `--repair-plugins` réécrit un **VST2 mort en VST3** en gardant le patch, via des « parsers » par plugin. `--dump-plugins` sert à la rétro-ingénierie | **Pas d'AU → VST3**. « Seule une poignée de plugins » est couverte. Pas de rapport lisible pour recréer un son. Ligne de commande uniquement |
| [OwlPlug](https://github.com/DropSnorz/OwlPlug/wiki/Projects-and-DAW-Support) | Gestionnaire de plugins qui compare les plugins d'un projet à ceux installés | Détection seulement |
| [als-tools](https://github.com/luizen/als-tools) (C#) | Indexe les sets dans une base et cherche par plugin | Ni presets ni réécriture |
| [ALFA](https://github.com/hemisus/alfa) | Explorateur en lecture seule (pistes, devices, paramètres, comparaison de versions) | Pas de réécriture |
| [PlugView](https://valery-kondakoff.gumroad.com/l/IZnyD) (Max for Live, 1 $) | Liste les plugins utilisés dans un set | Inventaire seulement |
| Ableton Live lui-même | — | Aucune migration automatique ([demande ouverte depuis 2022](https://forum.ableton.com/viewtopic.php?p=1817268)). Pour AU → VST, le support évoque des [standards différents](https://forum.ableton.com/viewtopic.php?p=1183915) |

**Positionnement :** personne ne couvre AU → VST3, ni la « fiche de recréation » lisible, ni une interface simple. Option à garder en tête : publier le décodeur NI comme parser pour abletoolz, ce qui serait une contribution à la communauté.

## 2. Ce que le prototype a établi

### Structure d'un `.als`
- Un fichier gzip contenant du XML, lisible avec la bibliothèque standard de Python. Version de Live dans `<Ableton Creator=…>`.
- Plugins : `AuPluginDevice` (AU) ou `PluginDevice` contenant `Vst3PluginInfo` (VST3) ou `VstPluginInfo` (VST2).
- Identité : AU = type/sous-type/fabricant (`aumu/Ni$H/-NI-` pour Massive X) ; VST3 = UID de 16 octets ; VST2 = ID de 4 caractères.
- État du plugin, en hexadécimal : AU = `Buffer` qui contient un plist Apple ; VST3 = `ProcessorState` (+ `ControllerState`) ; VST2 = `Buffer`.
- Paramètres exposés dans Live : `ParameterList` → `ParameterName`, `ParameterId`, valeur `Manual` (0–1), `AutomationTarget` et `ModulationTarget` (identifiants).
- Automations : `AutomationEnvelope` (arrangement) et `ClipEnvelope` (clips) pointent vers ces identifiants via `PointeeId`. Le prototype les relie aux paramètres : 3 enveloppes de clip trouvées sur « 7-Massive X ».

### Pièges découverts
- **Le chemin `LastPresetRef` est trompeur** (« Default.aupreset ») : c'est une référence du navigateur de Live, pas le preset réel.
- **Les valeurs `Manual` de Live ne sont pas fiables** pour les plugins : 0 % pour toutes les macros de Massive X, alors que l'état interne donne 49 %, 25 %… La valeur `0.1234567687` est une sentinelle de Live qui veut dire « valeur jamais lue ». C'est **l'état interne du plugin qui fait foi**.
- **Le nom de preset n'est connu que via l'état interne** : `meta/presetName` chez NI, `Preset Name` dans le JSON iZotope. Il n'y a pas de champ Live générique fiable.

### Décodage de l'état interne (là où se trouve le son)
- **Native Instruments, nouvelle génération (Massive X)** : plist AU → clé `vstdata` → en-tête de 16 octets + zlib → flux **msgpack** d'environ 3 600 valeurs nommées (`root/engine/unit1/audioPluginSlots/FilterSlot/selectedPlugin = BlueMonarkPlugin`…). On en tire le nom du preset, les macros (nom et valeur), les modules par slot (oscillateurs, filtre, FX, modulateurs), les modes et les tables. Le son peut ainsi être reconstruit à la main, réglage par réglage.
- **iZotope (Neutron, Ozone)** : en-tête + zlib → JSON « Context State », avec le nom de preset (« Warm Tube Bass »).
- **Battery 4** (ancien format NI « hsin ») : non décodé. Pour l'instant, seule la taille de l'état est rapportée.
- **Les autres plugins** auront chacun leur format. L'architecture prévoit un décodeur par famille, en commençant par les formats répandus : JUCE (XML ou binaire), FXP/FXB, NI, iZotope, u-he (texte), Vital (JSON).

## 3. Détection des plugins manquants (macOS)

| Format | Méthode | Fiabilité |
|---|---|---|
| AU | `Info.plist` de chaque `.component` → `AudioComponents` (type/sous-type/fabricant) | Exacte |
| VST3 | `Contents/Resources/moduleinfo.json` (SDK ≥ 3.7.5) → CID ; sinon le nom du bundle | Exacte ou probable |
| VST2 | Nom du bundle `.vst` | Probable |

À explorer :
- La **base de plugins de Live** (`~/Library/Application Support/Ableton/Live Database/`), qui dirait exactement ce que Live voit.
- Les préférences de Live (AU activés ou non). Dans ton cas, l'AU était peut-être installé mais désactivé.

Limite : l'inventaire ne fonctionne que sur le Mac. Dans le cloud, le statut affiché est « inconnu ».

## 4. Étape 5 : réécriture

### 5a. Même plugin, autre format (le cas Massive X AU → VST3)
Indices encourageants :
1. NI range l'état de l'AU dans une clé qui s'appelle littéralement **`vstdata`**. C'est probablement le même blob que l'état VST3.
2. Les UID VST3 du set suivent le schéma de compatibilité VST2 de Steinberg (`"VST" + ID à 4 caractères + nom`, ex. `VSTNBa4battery 4`, `VSTZNN3Neutron 3`). Celui de Massive X VST3 devrait être `VSTNi$Hmassive x`, à confirmer.
3. Les paramètres exposés à Live (01–16 = macros) ont des noms stables (« 02 Noise », « 03 Cutoff »). On peut donc faire la correspondance par nom, même si les identifiants diffèrent.

Plan de réécriture :
1. Partir d'un **gabarit** : un `Vst3PluginInfo` copié d'un set où Live a lui-même chargé le plugin en VST3. Il ne faut jamais inventer le XML de Live.
2. Y injecter l'état (`vstdata` → `ProcessorState`).
3. Reprendre la `ParameterList`, avec correspondance des `ParameterId` par nom, **en gardant les mêmes identifiants `AutomationTarget`/`ModulationTarget`**. Les automations et enveloppes de clip restent alors branchées sans rien toucher d'autre.
4. Écrire un **nouveau** fichier (`MySet [ReAble].als`) en gardant l'original intact, puis l'ouvrir dans Live pour valider.

**Test décisif** (environ 15 minutes de ton côté) : un set avec une piste Massive X **AU** et une piste Massive X **VST3** chargées avec le même preset, sauvegardé, puis le `.als` envoyé. Si les blobs sont identiques ou presque, 5a est faisable pour Massive X et probablement pour tous les plugins NI récents.

### 5b. Vers un autre plugin
Une traduction automatique (Massive X → Serum/Vital…) est irréaliste : les architectures de synthèse sont différentes. Ce qui est utile :
- la **fiche de recréation** du rapport, à suivre à la main ;
- l'option d'**exporter le résumé à une IA** pour proposer une approximation, par exemple un preset Vital, dont le format est du JSON ouvert. La fidélité serait faible, à classer comme expérimentation.

## 5. Risques

| Risque | Parade |
|---|---|
| Format `.als` non documenté et variable selon les versions de Live | Gabarits issus de vrais sets ; tests sur Live 11 et 12 ; ne jamais écraser l'original |
| Formats d'état propriétaires, propres à chaque plugin | Architecture à décodeurs ; commencer par NI, iZotope et JUCE ; afficher « non décodé » proprement |
| Set corrompu après réécriture | Nouveau fichier + sauvegarde horodatée + rapport des écarts ; validation dans Live |
| Licence : abletoolz est GPL | Code indépendant (aucune copie). Si on contribue, le décodeur NI peut être publié séparément |
| Mises à jour des plugins (format d'état qui change) | Versionner les décodeurs et tester sur des fixtures |

## 6. Architecture et choix techniques

- **Cœur : Python 3.10+**, avec la bibliothèque standard et `msgpack`. C'est le langage de l'écosystème (abletoolz) et il est rapide à prototyper. Modules : `alsfile` (gzip/XML), `extract` (Live), `decoders/` (un fichier par famille de plugins), `inventory` (plugins installés), `report` (Markdown/JSON), `cli`.
- **Interface « simple à utiliser »**, par étapes :
  1. ligne de commande + rapport (fait) ;
  2. **mini-app Mac** : glisser un dossier, voir le tableau, cliquer « Réparer ». Options : `pywebview` (garde le cœur Python, le plus rapide) ou SwiftUI qui appelle le CLI (plus natif) ;
  3. éventuellement un rapport HTML partageable.
- **Distribution** : outil perso d'abord. Une version publique, gratuite ou payante, est possible, puisque personne d'autre ne fait AU→VST3.

## 7. Feuille de route proposée

| Phase | Contenu | Effort estimé |
|---|---|---|
| 0 ✅ | Prototype : scan, extraction, décodeurs NI/iZotope, rapport, tests | fait |
| 1 | Valider sur ton Mac et tes vrais dossiers : inventaire, base de plugins de Live, cas des racks | 1 session |
| 2 | **Test décisif AU vs VST3** sur Massive X, puis réécriture 5a pour Massive X | 1–2 sessions |
| 3 | Généraliser 5a : gabarits par plugin, correspondance des paramètres, rapport des écarts | 2–3 sessions |
| 4 | Mini-app Mac (glisser-déposer, tableau, bouton Réparer) | 2–3 sessions |
| 5 | Décodeurs supplémentaires selon tes plugins les plus utilisés | au fil de l'eau |

## 8. Résultats de la Phase 1 (scan MesProjets, 7 oct. 2026)

- 365 sets, 1821 plugins tiers, 979 « manquants » → après qualification par famille : voir `reable-report.md` (sections « À réinstaller », « Même famille installée », « Installé dans un autre format »).
- UID VST3 réel de Massive X : `5653544E6924486D6173736976652078` = `VSTNi$Hmassive x` (prédiction confirmée).
- Aucun set de MesProjets n'a le même plugin en AU et en VST3 ; le test décisif AU↔VST3 reste à faire avec un set dédié.
- `reable compare` (même plugin, VST2 vs VST3, même set) :
  - **Ozone 8** et **Neutron 3** : schéma d'état **identique** (1979 / 1257 clés), seules les valeurs et le `PluginUUID` diffèrent. Ce sont deux instances réglées différemment, pas un même preset : le schéma est compatible entre formats, mais l'égalité de valeurs n'est pas prouvée.
  - **Play** et **Abbey Road One** : états binaires non décodés, tailles différentes (676 Ko / 389 Ko ; 29 Ko / 38 Ko) → pas de conclusion.
- Pour trancher : un set où **la même instance** (même preset) est chargée en deux formats.

### Test AU vs VST3 — « Test Plugins AU VST3.als » (Live 12.4.6, 7 oct. 2026)
Piste 1 : Massive X **AU** (preset « 4am Catbus »), piste 2 : Massive X **VST3** (preset « Abstract City »), valeurs modifiées. Ozone 10 VST3 sur Main.
- **Même conteneur d'état** : AU `vstdata` (33 022 o) et VST3 `ProcessorState` (32 054 o) commencent par le même en-tête `02000000 03000000 <taille LE sur 4 o> …` suivi d'un flux zlib (`78 9c`). Taille = longueur totale − 12 dans les deux cas. Le même décodeur msgpack lit les deux.
- `ControllerState` VST3 est **vide** : tout l'état est dans `ProcessorState`.
- UID VST3 confirmé : `5653544E6924486D6173736976652078`. AU : `aumu/Ni$H/-NI-`.
- Paramètres : Live n'expose que les paramètres « configurés » (ici « Morpher - X/Y », `ParameterId` = −1) ; 256 emplacements côté AU, 128 côté VST3. Le remapping « par nom » ne porte donc que sur les paramètres configurés ; les autres emplacements sont vides.
- Comparaison des valeurs : impossible (deux presets différents). Pas de preuve que Live accepte un AU `vstdata` injecté dans un `ProcessorState` : c'est le prochain test (prototype de réécriture, puis ouverture dans Live).

### Test AU vs VST3, même preset « Abstract City » (version du 7 oct. 12:46)
Modifications faites sur les deux pistes : matrice (emplacement 3) + LFO Amt à 100 %.
- Schéma d'état **identique** (3726 clés des deux côtés), 3716 valeurs égales ; la matrice et le LFO sont identiques en AU et VST3.
- Le fichier preset NI (`/Users/Shared/Drive Library/Presets/Abstract City.nksf`, chunk `PCHK` = `01000000` + même conteneur `02000000 0x000000 <taille> zlib`) se décode avec le même décodeur. Macros du preset : `[0, 0, 0, 0, 0, 0.190625, 0.390625, 0.2125]`.
- **VST3 = preset exact** (macro 1 = 1.0 à cause du LFO). **AU : macros 2–8 différentes du preset** (0.19, 0.42, 0.75, 0.66, 0.36, 0.27, 0.84), mais cohérentes en interne (Decay/Attack/Release = macros 6/7/8). Cause non établie.
- Aucune valeur n'est stockée hors du `.als` : l'état complet (macros, knobs, matrice) est dans `vstdata` / `ProcessorState`.

## 9. Validation dans Live (7 oct. 2026) — tous les tests passent
Résultats donnés par l'auteur après ouverture dans Live 12 :
- **AU → VST3, Massive X** (`Test Plugins AU VST3 [ReAble].als`) : OK, état et macros conservés.
- **G1 Massive VST2 → VST3** (2 instances) : OK.
- **G2 / G2b Kontakt VST2 → Kontakt 8 VST3** (1 et 2 instances) : OK.
- **G3 Kontakt 5 → Kontakt 8 VST3** : OK (famille de plugins différente, même conteneur d'état).
- **G5 notes de device et noms de piste** (accents, emoji, texte long, JSON) : OK.

Conclusions :
1. Pour les plugins **Native Instruments** (conteneur `<taille> 00000000 01000000` ou `02000000 03000000`), la conversion d'un format à l'autre se résume à copier le bloc d'état dans un device VST3 gabarit, avec reprise des Id d'automation.
2. Le changement de version dans la même famille (Kontakt 5 → 8) fonctionne.
3. La traçabilité par la note de device (`Annotation`) est utilisable.
4. Limites toujours valables : sets anciens (Live < 11, schéma différent), iZotope (conteneur réordonné entre VST2 et VST3), autres éditeurs non testés, fidélité audio non mesurée (T6).

## 10. Validation dans Live — options de workflow et restauration (9 oct. 2026)
Validé par l'auteur dans Live 12 :
- **duplicate_track** (H1) : après deux correctifs (Id globaux `ControllerTargets.N`/`*ModulationTarget` ; attribut `Id` ajouté à tort sur `<Target>`), le set s'ouvre ; piste d'origine mutée, copie en VST3.
- **Texte d'info de piste** (`Name/Annotation`) : écrit et lu correctement ; le texte de l'utilisateur est conservé.
- **restore** : R1 (duplication), R2 (remplacement, original embarqué), R3 (remplacement, depuis le set d'origine) s'ouvrent sans problème.
Garde-fous ajoutés : unicité des Id globaux, contrôle de schéma des attributs ; un échec bloque l'écriture.
Non testé : `keep_device` (effets), restauration d'un set modifié après conversion.
