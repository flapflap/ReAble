# ReAble — décisions de workflow et options

_Document de conception, 7 oct. 2026. Chaque ligne = une décision configurable (dataclass `ConvertOptions` → profil JSON → écran de l'interface).
Défaut = ce qui est le plus sûr pour un premier lancement. Faisabilité : ✅ simple · 🟡 faisable avec soin · 🔴 risqué/à valider dans Live._

## A. Les trois décisions demandées

### A1. Copier la piste avec le nouveau plugin, ou remplacer ?
| Mode (`replace_mode`) | Résultat | Faisabilité |
|---|---|---|
| `replace` (défaut) | Le device d'origine est remplacé sur place par le VST3. | ✅ fait |
| `keep_device` | Le VST3 est inséré **à côté** de l'ancien device, qui reste dans la chaîne mais **désactivé** (et, s'il est absent du Mac, Live l'affiche comme plugin manquant). Aucune duplication de piste. | 🟡 (Id neufs pour l'ancien device, ordre dans la chaîne) |
| `duplicate_track` | La piste entière est dupliquée : l'originale est **mutée et désactivée** (ou repliée/grisée), la copie porte le VST3. | 🔴 (Id de tous les clips/automations, routages, groupes, sidechains, retours) |

Sous-options : `original_state` = `muted` / `deactivated` / `hidden` (Live 12 permet de masquer des pistes) ; `position` = juste après / à la fin.
Recommandation : proposer `replace` et `keep_device` dès la v1 ; `duplicate_track` seulement après validation dans Live.

### A2. Renommer
| Option | Valeurs |
|---|---|
| `rename_target` | `track` · `device` · `clips` (premier clip) · `none` |
| `rename_mode` | `none` · `suffix` · `prefix` · `template` |
| `rename_template` | texte libre avec variables : `{track}` nom actuel · `{plugin}` · `{from}` format d'origine · `{to}` format cible · `{preset}` nom du preset (si décodé) · `{date}` · `{n}` numéro |
| `rename_missing_preset` | `omit` (défaut) · `use_plugin_name` · `question_mark` |

Exemples : `{track} [{from}→{to}]` → `Lead [AU→VST3]` ; `{track} — {preset}` → `Lead — Abstract City` ; `{preset}` seul.
Le nom de preset n'est connu que pour les plugins décodés (NI, iZotope) ; sinon `{preset}` est vide selon `rename_missing_preset`.
Idempotence : on ne rajoute pas deux fois la même étiquette. ✅

### A3. Pistes sans plugin (ou plugin non convertible) : écrire une info ?
Interprétation à confirmer (voir « Questions ») : écrire, pour **les pistes dont on ne peut pas convertir le plugin** (manquant, famille non gérée, set trop ancien), une fiche « plugin + preset » pour pouvoir recréer le son à la main.

| Option (`info_*`) | Valeurs |
|---|---|
| `info_for` | `converted` · `unconvertible` (plugin absent sans remplacement) · `all_plugin_tracks` · `none` |
| `info_where` (plusieurs possibles) | `device_note` (champ *Info Text* du device — le plus fiable) · `track_name` (suffixe court) · `clip_name` (premier clip de la piste) · `locator` (marqueur au début du morceau : « Piste X : Plugin / Preset ») · `sidecar` (fichier Markdown/JSON à côté du set, toujours recommandé) |
| `info_content` | cases à cocher : plugin · format · fabricant · preset · paramètres macros · automations · état installé/manquant · suggestion de remplacement |
| `info_when_no_device` | une piste sans device ne peut pas porter de note : utiliser `track_name`, `clip_name`, `locator` ou `sidecar` |

Faisabilité : `device_note` ✅ (testé), `track_name` ✅ (testé), `clip_name` 🟡, `locator` 🟡 (XML des marqueurs à copier d'un vrai set), `sidecar` ✅.
**Correction (9 oct.)** : toutes les pistes ont un *texte d'info* (`Name/Annotation`, affiché en bas à gauche dans Live) dans toutes les versions de Live. Il est maintenant utilisé : option `track_info` (modèle `track_info_template`, texte de l'utilisateur conservé avant le bloc ReAble ; une phrase est aussi écrite sur la piste d'origine en `duplicate_track`).

## B. Autres décisions auxquelles je pense

### B1. Portée : quoi convertir
- `scope_sets` : dossier entier · sélection de sets · filtre par version de Live, par date, par nom (motif).
- `only_missing` : seulement les plugins absents du Mac (défaut) · tous.
- `mapping` : **table source → cible modifiable par l'utilisateur** (ex. `Kontakt 5 → Kontakt 8`, `Massive → Massive X` interdit car non compatible) avec `skip` par ligne.
- `families` : familles autorisées (défaut : celles validées dans Live).
- `unvalidated_plugins` : `block` (défaut) · `try` (autorise un plugin non validé, avec avertissement).
- `target_not_installed` : `block` (défaut) · `convert_anyway` (utile pour préparer un Mac qui n'a pas encore le plugin).
- `multiple_targets` : si plusieurs versions installées (Kontakt 7 et 8) → `latest` (défaut) · `ask` · `fixed:<nom>`.

### B2. Sortie et sécurité
- `output_mode` : `new_file_beside` (défaut, suffixe) · `mirror_folder` · `in_place_with_backup` (jamais par défaut).
- `output_name_template` : `{name} [ReAble]` modifiable.
- `if_exists` : `skip` · `overwrite` · `number` (défaut).
- `backup_originals` : copie horodatée avant toute écriture en place.
- `verify_after_write` : relire le fichier, vérifier les Id uniques, les enveloppes, et que l'état injecté est identique (défaut : oui).
- `dry_run` : toujours disponible ; l'interface montre le plan avant d'écrire.
- `manifest` : journal de tout ce qui a été écrit, pour un **« tout annuler »** d'un lot.

### B3. Traçabilité
- `write_note` (oui) · `embed_original` (oui) · `max_embed_kb` (100) · `note_language` · `note_content` (cases comme `info_content`).
- `restore_policy` : depuis la note · depuis le set d'origine.

### B4. Cas limites de la conversion
- `unmapped_parameter` (automation sur un paramètre absent du gabarit) : `warn` (défaut) · `skip_device` · `skip_set`.
- `keep_device_state` : reprendre On/Off, nom d'utilisateur, réglages MPE de l'ancien device (défaut : oui).
- `racks_and_returns` : inclure les devices dans les racks/retours/master (défaut : oui).
- `frozen_tracks` : `skip` · `warn` (pistes gelées : le fichier audio gelé reste lié à l'ancien plugin).
- `old_sets` (Live ≤ 10) : `list_for_resave` (défaut : les lister dans un fichier) · `skip` · `try_experimental`.
- `template_source` : gabarit automatique (le plus récent trouvé) · dossier de gabarits choisi · set indiqué par l'utilisateur.

### B5. Rapports
- `report_formats` : Markdown · JSON · CSV ; `report_scope` : par lot · par set.
- **Fiche de recréation** (le but initial de ReAble) pour les plugins qu'on ne sait pas convertir : plugin, preset, macros, automations — déjà produite par `scan`, à rattacher à `info_where=sidecar`.

### B6. Interface et confort
- Profils de réglages sauvegardés (JSON) : « Prudent », « Complet », « Personnalisé », partagés entre CLI et interface.
- Progression, annulation en cours de lot, journal.
- Prévisualisation d'un set : avant / après (liste des devices, noms de pistes).
- Langue de l'interface et des notes (fr/en).

## C. Modèle de configuration
Un seul objet `Profile` (JSON) alimente CLI et interface :

```json
{
  "replace_mode": "replace",
  "rename": {"target": "track", "mode": "template", "template": "{track} [{from}→{to}]", "missing_preset": "omit"},
  "info": {"for": "unconvertible", "where": ["device_note", "sidecar"], "content": ["plugin", "preset", "status"]},
  "scope": {"only_missing": true, "families": ["kontakt", "massive", "massive x", "fm8", "absynth", "battery"], "mapping": {}},
  "output": {"mode": "new_file_beside", "name_template": "{name} [ReAble]", "if_exists": "number", "verify": true},
  "trace": {"write_note": true, "embed_original": true, "max_embed_kb": 100},
  "edge_cases": {"unmapped_parameter": "warn", "frozen_tracks": "warn", "old_sets": "list_for_resave"}
}
```

## D. Décisions prises (7-9 oct. 2026)
1. **A3** : une piste sans plugin n'a pas de son → aucune info à écrire pour elle. L'option `info_*` est abandonnée.
2. **A1** : on ne peut pas avoir deux instruments sur une même piste. Donc : instrument → `replace` ou `duplicate_track` (piste copie, originale **mutée** et suffixée `[original]`) ; effets → aussi `keep_device` (ancien effet conservé, désactivé). Un instrument demandé en `keep_device` passe en `duplicate_track`.
3. **A2/visibilité** : l'information passe par le **nom de piste** (modèle à variables `{track} {plugin} {from} {to} {preset} {date}`).
4. **Réglages** : un seul écran de réglages (pas de profils prédéfinis) ; le profil JSON (`docs/profile-example.json`) sert à les enregistrer.

Implémenté : `replace_mode`, `mute_original`, `original_suffix`, `rename_target/template`, `missing_preset`, `mapping`, `skip_plugins`, profil JSON (`--profile`, `--save-profile`), `restore` d'une duplication (supprime la copie, réactive l'originale).
Non testé dans Live : `duplicate_track`, `keep_device` (aucun effet NI avec gabarit dans le corpus).

## E. Questions ouvertes (anciennes)
1. **A3** : par « pistes sans plugin », faut-il comprendre (a) les pistes dont le plugin est introuvable et non convertible, (b) les pistes qu'on a converties mais pour lesquelles on veut aussi une trace lisible, ou (c) autre chose ?
2. **A1** : `keep_device` (ancien device désactivé dans la même piste) suffit-il comme « copie », ou veux-tu vraiment une **piste dupliquée** ?
3. Où l'information doit-elle être **visible dans Live** en priorité : nom de piste, note du device, ou marqueur (locator) ?
4. Souhaites-tu des **profils** (« Prudent » / « Complet ») ou un seul écran de réglages ?
