# ReAble — permettre aux utilisateurs d'ajouter leurs plugins

_Étude, 9 oct. 2026. Point de départ : aujourd'hui, ce que sait ReAble est écrit en dur pour les plugins de l'auteur (NI, iZotope). Un utilisateur qui a d'autres plugins doit pouvoir les ajouter sans modifier le code._

## 1. Ce qui est déjà générique, ce qui ne l'est pas

| Brique | État | Pourquoi |
|---|---|---|
| Inventaire des plugins installés | ✅ générique | lit les dossiers macOS |
| Gabarits VST3 | ✅ générique | pris dans les sets de l'utilisateur (`--templates`) ; rien d'inventé |
| Correspondances/exclusions (`mapping`, `skip_plugins`) | ✅ générique | réglages de l'utilisateur |
| Réécriture du XML, Id, notes, restore, contrôles d'intégrité | ✅ générique | indépendants du plugin |
| **Reconnaître la famille d'un plugin** (`families.py`) | ❌ en dur | liste de motifs (Kontakt, Ozone…) |
| **Quelles familles sont sûres** (`COMPATIBLE`, `EXPERIMENTAL`) | ❌ en dur | résultat de MES tests dans Live |
| **Comment convertir l'état** (`adapters.py`) | ❌ en dur, par famille | NI = copie, iZotope = ré-emballage |
| **Lire le nom du preset** (`decoders/`) | ❌ en dur, par famille | NI msgpack, iZotope JSON |

Seules les quatre dernières lignes sont spécifiques à un plugin. Tout le reste fonctionne déjà pour n'importe quel plugin.

## 2. Ce qu'on sait d'un plugin inconnu sans le tester — la commande `probe`

`./run.sh probe <dossier>` classe automatiquement le **conteneur d'état** de chaque plugin des sets. Sur MesProjets (1821 instances, 83 plugins) :

| Statut | Plugins | Instances | Signification |
|---|---|---|---|
| validé | 11 | 683 | conversion testée dans Live (NI : Kontakt, Massive, FM8, Battery, Absynth…) |
| en test | 6 | 170 | adaptateur écrit, en attente de validation (Ozone) |
| à tester | 19 | 396 | conteneur connu et copiable en principe (NI étiquetés : Replika, RC 48, Guitar Rig ; zlib : Play, EW ; JUCE `VstW` : LABS, Abbey Road ; iZotope : Neutron) mais jamais essayé dans Live |
| adaptateur à écrire | 47 | 572 | format propriétaire/texte/XML/vide (FabFilter, Reason Rack, Opus, Valhalla, kHs…) |

→ Pour un nouvel utilisateur, **environ 60 % des instances** (validées + en test + à tester) pourraient être couvertes sans écrire de code, à condition de pouvoir les **valider** dans Live. Le reste exige un adaptateur dédié ou n'est pas convertible.

## 3. Proposition

### 3.1 Des « définitions de plugin » en données, pas en code
Un fichier JSON par plugin ou par famille, chargé depuis deux endroits : **intégrées** (livrées avec ReAble) et **utilisateur** (`~/Library/Application Support/ReAble/plugins/`).

```json
{
  "id": "ozone",
  "match": ["^(izotope )?ozone\\b"],
  "vendor": "iZotope",
  "adapter": "izotope",
  "decoder": "izotope_json",
  "upgrade_to": ["Ozone 10"],
  "status": "experimental",
  "validated": [],
  "notes": "Ozone 9 et 10 partagent l'identifiant du conteneur ; Ozone 8 non."
}
```

- `adapter` : choisi dans une **bibliothèque d'adaptateurs génériques** livrée avec l'outil (`container-copy` : copie si la forme du conteneur est identique ; `izotope` : ré-emballage ; `none` : état par défaut). L'utilisateur n'écrit pas de code : il en choisit un.
- `status` : `validated` (testé dans Live par quelqu'un, avec version de Live et date) · `experimental` (essayable, avertissement) · `unsupported`.
- Les définitions intégrées remplacent `families.py`, `COMPATIBLE` et `EXPERIMENTAL`.

### 3.2 Flux « j'ajoute un plugin »
1. **Sonder** : l'analyse du dossier liste, dans un onglet *Plugins*, tout ce qui est utilisé, avec son statut (couvert / à tester / non couvert) et le conteneur détecté.
2. **Proposer** : pour un plugin « à tester », ReAble propose automatiquement un adaptateur selon le conteneur (`container-copy` pour NI étiqueté, JUCE, zlib ; `izotope` pour iZotope) et un **niveau de confiance**. Si le plugin existe dans deux formats ou deux versions dans les sets de l'utilisateur, il compare les états : forme identique → confiance haute.
3. **Générer un pack de test** (déjà fait à la main pour G1–G6, H, Ozone) : quelques sets dans un dossier, dont chaque conversion est tentée avec les variantes utiles (`transfer`, `header`, `none`).
4. **Valider** : l'utilisateur ouvre les sets dans Live et répond par un clic (« fonctionne » / « ne fonctionne pas » + choix de la variante). La réponse est enregistrée dans sa définition (`validated` avec la date et la version de Live).
5. **Utiliser** : le plugin passe en `validated` pour cet utilisateur.
6. **Partager** (plus tard) : export d'une définition validée, import par d'autres, éventuellement un registre communautaire avec la provenance.

### 3.3 Garde-fous (non négociables)
- Un plugin non validé est **bloqué par défaut** ; il faut l'activer explicitement (comme `--family ozone` aujourd'hui) et l'écran affiche « expérimental ».
- Chaque conversion écrit la **note de traçabilité** et reste **restaurable** (`restore`).
- Les contrôles d'intégrité (Id uniques, schéma des attributs) s'appliquent à tous les plugins, y compris ajoutés par l'utilisateur : un fichier que Live refuserait n'est jamais écrit.
- Un set converti n'écrase jamais l'original.

### 3.4 Limites à annoncer honnêtement
- **Pas de garantie automatique** : « le conteneur est le même » n'implique pas que le plugin relise l'état. Seul un test dans Live le prouve (c'est pourquoi l'étape 4 existe).
- Les plugins à état **propriétaire** (FabFilter texte, Reason Rack, Opus…) demandent un adaptateur écrit par un développeur ; l'utilisateur ne peut que les signaler. Pour eux, l'outil se limite à la **fiche de recréation** (nom du plugin, preset, paramètres connus dans Live).
- Les sets de Live ≤ 10 doivent d'abord être ré-enregistrés dans Live 12 (indépendant des plugins).
- Un plugin sans VST3 installé ou sans gabarit dans les sets analysés ne peut pas être converti : l'écran guide l'utilisateur (« chargez-le une fois en VST3 dans un set »).

## 4. Plan de réalisation (après l'interface de base)
| Étape | Contenu | Valeur |
|---|---|---|
| E1 | Charger les définitions depuis JSON (intégrées + utilisateur) ; migrer `families.py`/`COMPATIBLE`/`EXPERIMENTAL` | un utilisateur peut ajouter une famille en éditant un fichier |
| E2 | Bibliothèque d'adaptateurs génériques (`container-copy`, `izotope`, `none`) paramétrables dans la définition | ajout sans code |
| E3 | Onglet *Plugins* dans l'interface : liste, statuts, activer/désactiver, « Proposer » | découverte guidée |
| E4 | Pack de test + enregistrement du résultat (`validate`) | validation par l'utilisateur |
| E5 | Export/import de définitions | partage |

`probe` (déjà écrit) fournit la détection pour E3.

## 5. Décisions prises (9 oct. 2026)
1. **Validation locale, partageable dans un dépôt partagé, en option.**
2. **Un plugin non validé est bloqué** par défaut.
3. **Les définitions livrées = ce que l'auteur a validé** ; le reste est « à tester ».
4. **Deux dépôts GitHub + une couche locale** (voir §6).
5. **Programme bêta** pour enrichir la base (voir §7).

## 6. Architecture : deux dépôts et une couche locale
| | Dépôt de code `reable` | Dépôt de données `reable-definitions` | Local |
|---|---|---|---|
| Contenu | l'application, le moteur, les adaptateurs génériques, l'interface | une définition JSON par plugin (`definitions/<éditeur>/<plugin>.json`), le schéma, l'outil de validation, `reports/` (résultats bêta) | `~/Library/Application Support/ReAble/` : définitions de l'utilisateur, réglages |
| Visibilité | public, open source | public, démarre avec les données validées de l'auteur | privé à l'utilisateur |
| Évolue | à chaque version du code | sans nouvelle version de l'application (`reable plugins sync`) | à chaque test de l'utilisateur |

Couches de lecture (la dernière gagne) : instantané livré avec une version (généré à la publication, absent du dépôt de code) → dépôt de définitions cloné (`sync`) et dossiers listés dans les réglages → fichiers importés → **définitions locales**.
Le code ne contient aucune définition : les tests utilisent une copie de test (`tests/definitions_fixture/`).
Mise en place déjà faite : `reable plugins list | add | validate | export | import | sync | config | beta`.

## 7. Programme bêta
**But** : enrichir la base `reable-definitions` avec des résultats de tests réels, sans jamais envoyer de données d'utilisateur.
- **Opt-in explicite** : `reable plugins beta on` (désactivé par défaut). Il génère un pseudonyme aléatoire, sans lien avec l'identité.
- **Ce qui peut être partagé** (`plugins export --beta`) : identifiant et motif du plugin, éditeur, adaptateur, statut, variante testée, résultat (`ok`/`ko`), versions de Live, macOS et ReAble. **Jamais** de chemin, de nom de set, de piste ou de preset, ni de contenu musical, ni de notes libres.
- **Transparence** : la commande affiche à l'écran exactement le contenu avant tout partage ; **rien n'est envoyé automatiquement**. L'utilisateur joint le fichier à une *issue* « Résultat bêta » ou ouvre une PR dans `reports/`.
- **Promotion** (règles dans le dépôt de données) : `experimental` → `validated` après un test des mainteneurs ou deux bêta-testeurs indépendants sur la même variante.
- **Phase suivante** : un bouton « Envoyer mon résultat » dans l'interface qui prépare l'issue GitHub pré-remplie (toujours validée par l'utilisateur).

## 8. Décisions restantes
- Licence du dépôt de données et du dépôt de code.
- Organisation GitHub, noms et visibilité des deux dépôts (création = action publique, à décider par l'auteur).
- Mode d'instantané livré avec l'application : signature des définitions ? (à étudier si le dépôt devient communautaire).
1. **Où vit la validation ?** Locale à l'utilisateur seulement, ou partagée (registre) ? La seconde donne de la valeur mais exige confiance et provenance.
2. **Niveau d'avertissement** pour un plugin « à tester » : bloqué par défaut (recommandé) ou proposé avec un avertissement.
3. **Périmètre public** : les définitions intégrées livrées ne contiennent que ce que l'auteur a validé dans Live (11 plugins NI) ; le reste est « à tester ».
