# ReAble — brief de passation pour Claude Design

_Document autonome : tout ce qu'il faut pour concevoir l'interface se trouve ici. Langue de l'interface : **français**._

## 0. Prompt court à coller
> Conçois l'interface d'une petite application Mac nommée **ReAble**, qui répare des projets Ableton Live dont des plugins ne sont plus installés (elle les remplace par la version VST3 ou plus récente). Écran unique, très **simple et didactique**, avec un **suivi de progression** clair et un bouton **Arrêter** toujours disponible. Propose **2 à 3 directions visuelles** de l'écran principal (étapes ① Choisir, ② Comprendre, ③ Convertir, bilan), **en thème clair et sombre**, en suivant le brief ci-dessous (§3 à §9). Ton : calme, précis, rassurant. Pas de référence imposée.

## 1. Le produit en trois phrases
Un producteur de musique a des centaines de projets Ableton Live. Certains utilisent des plugins qu'il n'a plus (anciennes versions, ancien format). **ReAble** analyse ses dossiers, dit clairement ce qui peut être réparé, puis écrit des **copies** des projets avec le plugin de remplacement, en gardant autant que possible les réglages. **Les projets d'origine ne sont jamais modifiés**, et chaque conversion peut être annulée.

## 2. L'utilisateur et le ton
- **Qui** : producteur/compositeur, à l'aise avec Ableton, **pas technicien** (il ne connaît pas « AU / VST2 / VST3 », « état du plugin »). Il a peur d'abîmer ses projets.
- **Ce qu'il veut ressentir** : « je comprends ce qui va se passer avant de cliquer », « je ne risque rien », « je peux arrêter à tout moment ».
- **Ton des textes** : phrases courtes, concrètes, au présent, tutoiement exclu (vouvoiement neutre ou forme impersonnelle). Jamais alarmiste. Le jargon est expliqué au premier usage (infobulle « C'est quoi ? »).

## 3. Contraintes techniques
- **Fenêtre** : application Mac (fenêtre web dans pywebview). Taille par défaut **1100 × 720 px**, minimum **900 × 620**. Pas de version mobile.
- **Thèmes** : clair et sombre, suivant le système (`prefers-color-scheme`). Fournir les deux.
- **Implémentation** : HTML + CSS + JavaScript sans framework ; **tout le style doit se ramener à des jetons CSS** (voir §10). Pas d'images matricielles. Icônes en **SVG en ligne**, un seul jeu, jamais d'emoji comme icône.
- **Accessibilité** : contraste ≥ 4,5:1 ; focus clavier visible ; zones cliquables ≥ 44 px ; l'état n'est **jamais** indiqué par la couleur seule (icône + mot) ; progression annoncée aux lecteurs d'écran ; respect de `prefers-reduced-motion`.

## 4. Structure de l'écran principal
```
┌────────────────────────────────────────────────────────────────────────────┐
│ ReAble        ① Choisir  ─  ② Comprendre  ─  ③ Convertir      Plugins   │  ← en-tête + étapes
├───────────────────────────────────────────────────────┬────────────────────┤
│  ZONE PRINCIPALE (change selon l'étape)               │  RÉGLAGES           │
│                                                       │  (panneau à droite, │
│                                                       │   sections repliées)│
├───────────────────────────────────────────────────────┴────────────────────┤
│  Bandeau discret : « Vos projets d'origine ne sont jamais modifiés. »      │
└────────────────────────────────────────────────────────────────────────────┘
```
- Les **trois étapes sont toujours visibles** (indiquent où l'on en est ; les étapes passées sont cliquables).
- Un **seul bouton principal** par étape (le seul à porter la couleur d'accent).
- Le panneau **Réglages** est utile mais jamais obligatoire : valeurs par défaut sûres, sections repliées.

## 5. Écrans et états à concevoir
Pour **chaque direction visuelle**, en **clair et sombre**.

| # | Écran / état | Ce qu'il doit montrer |
|---|---|---|
| A1 | **① Choisir — vide** | Invitation à choisir un dossier (zone de dépôt + bouton « Choisir un dossier… »), phrase d'explication en 2 lignes, bandeau de réassurance |
| A2 | **① Choisir — dossier choisi** | Chemin affiché (police à chasse fixe), nombre de projets trouvés, bouton principal « Analyser » |
| B | **Analyse en cours** | Progression (voir §6) : « Lecture des projets… 120 / 365 », bouton **Arrêter** |
| C1 | **② Comprendre — résumé et groupes** | Résumé en phrases + liste de **groupes de conversion** (voir §7) + bouton principal « Convertir 21 projets » et bouton secondaire « Essai à blanc » |
| C2 | **② — un groupe déplié** | Liste des projets du groupe avec cases à cocher, nom du projet, piste/plugin concerné, lien « Pourquoi ? » |
| C3 | **② — réglages ouverts** | Panneau Réglages avec aperçu en direct du nom de piste (avant → après) |
| D1 | **③ Conversion en cours** | Suivi complet (voir §6) |
| D2 | **③ — arrêt en cours** | Bouton « Arrêt en cours… » désactivé + message « Le projet en cours est abandonné proprement » |
| E1 | **Bilan — succès** | « 24 projets convertis, 0 erreur » + actions : Ouvrir le dossier · Copier la liste · Annuler cette conversion · Que vérifier dans Live ? |
| E2 | **Bilan — arrêté** | « Arrêté : 14 faits, 37 non traités » + **Reprendre** · **Annuler ce qui a été fait** |
| F1 | **Rien à convertir** | Illustration sobre (SVG) + explication + que faire |
| F2 | **Erreur** | Message clair, ce qui est sûr (« aucun projet modifié »), action de reprise |
| G | **Onglet Plugins** | Liste de plugins avec statut (validé · expérimental/bloqué · non pris en charge), boutons Ajouter · J'ai testé dans Live · Exporter pour la bêta · Synchroniser |
| H | **Boîte de confirmation** | Fermer la fenêtre pendant une tâche : « Arrêter et fermer ? » |

Composants à définir : étapes (stepper), carte de groupe de conversion, badge d'état, barre de progression et ses phases, journal, bouton **Arrêter** (états : normal, survol, focus, appuyé, « arrêt en cours », désactivé), zone de dépôt, champ de chemin, interrupteurs et listes de choix du panneau Réglages, infobulle de glossaire, toast, boîte de dialogue.

## 6. Le suivi de progression (point crucial)
Doit être **lisible d'un coup d'œil** et **toujours arrêtable**.
- **Barre globale** : projets faits / total (« 14 / 51 »), pourcentage implicite par la barre.
- **Temps** : écoulé et **reste estimé** (« ≈ 5 min 30 »).
- **Élément en cours** : nom du projet + **phase** sur 4 pas : lecture → conversion → contrôle → écriture (le pas actif est mis en évidence).
- **Compteurs par résultat** (icône + nombre + mot) : convertis · réglages par défaut · ignorés · erreurs.
- **Journal** repliable, filtrable (tout · avertissements · erreurs), horodaté, défilement automatique pouvant être suspendu.
- **Bouton Arrêter** : toujours visible, jamais caché dans un menu, **sans confirmation** (l'arrêt est sûr). Après le clic : « Arrêt en cours… », puis bilan d'arrêt.
- La même présentation sert pour l'analyse, l'essai à blanc, la conversion et la restauration (seul le verbe change).

## 7. Contenu : textes et données d'exemple
**Résumé de l'étape ② (exemple réel)**
> **21 projets seront convertis.** Les réglages de 18 Ozone 9 seront repris dans Ozone 10. Pour 3 projets, Ozone 10 démarrera avec ses réglages par défaut et le nom de l'ancien preset sera noté sur la piste.
> **66 projets sont trop anciens** : ouvrez-les dans Live 12 et enregistrez-les, puis relancez l'analyse.

**Groupes de conversion (étape ②)**
| Étiquette | Titre | Détail | Action |
|---|---|---|---|
| Validé | **Ozone 9 → Ozone 10** · 18 projets | Vos réglages seront repris. | Voir les projets |
| Réglages par défaut | **Ozone 8 → Ozone 10** · 42 projets | Ozone 10 ne sait pas lire les réglages d'Ozone 8 : il démarre avec ses réglages par défaut. Le nom de l'ancien preset est noté sur la piste. | Voir les projets |
| Validé | **Kontakt 5 → Kontakt 8** · 7 projets | La piste est dupliquée : l'originale reste, en sourdine, à côté de la copie. | Voir les projets |
| Action requise | **66 projets trop anciens** | Ces projets doivent d'abord être ouverts et enregistrés dans Live 12. | Copier la liste · Ouvrir le dossier |
| Non pris en charge | **245 plugins sans équivalent** (FabFilter, Play…) | ReAble ne sait pas encore les convertir. | Voir lesquels |

**Projets d'exemple** (anonymes, à réutiliser dans les maquettes) : « Projet 12 », « Projet 24 », « Projet K », « Projet I — Action March v2 », « Projet L », « Projet M », « Projet J — WIP ». Chemin d'exemple : `~/Music/MesProjets`.

**Réglages (panneau)** — chaque réglage a un nom clair, un défaut sûr, et une phrase d'aide :
1. *Que faire de la piste d'origine ?* — « Dupliquer la piste (l'originale reste en sourdine) » · « Remplacer sur place ».
2. *Nom des pistes converties* — modèle `{piste} [{de}→{vers}]`, **aperçu en direct** : « Lead  →  Lead [VST2→VST3] ».
3. *Texte d'information de la piste* — activé ; aperçu de 4 lignes (« Converti par ReAble le 2026-10-09 / Ozone 9 : VST2 → VST3 / Preset d'origine : … / … »).
4. *Plugins à convertir* — liste de familles avec statut ; les non validés sont grisés « bloqué ».
5. *Où écrire les copies* — « À côté des originaux » (conseillé) · « Dans un autre dossier ».
6. *Si la copie existe déjà* — « Ne pas la refaire » (conseillé) · « La remplacer » · « Numéroter ».

**Glossaire (infobulles « C'est quoi ? »)** : *AU, VST2, VST3* — « différents formats de plugins ; Ableton Live 12 préfère le VST3 » ; *état du plugin* — « l'ensemble des réglages et du preset enregistrés dans le projet » ; *piste dupliquée* — « une copie de la piste avec le nouveau plugin ; l'originale reste, en sourdine ».

**Messages d'état** : « Analyse terminée : 365 projets lus. » · « Essai à blanc : rien n'a été écrit. » · « Conversion terminée. » · « Arrêté : 14 faits, 37 non traités. » · « Aucun projet n'a été modifié. »

## 8. Direction visuelle demandée (point de départ, à explorer librement)
**« Calme et précise »** : l'outil touche à des projets de musique, il doit inspirer confiance, pas exciter.
- Neutres chauds, **un seul accent** sobre pour l'action principale ; couleurs d'état désaturées (vert validé, ambre attention, rouge erreur, gris non pris en charge), toujours doublées d'icône et de mot.
- Beaucoup d'air, hiérarchie typographique forte, peu de bordures, ombres très légères.
- Police système (SF Pro) ; chemins et noms de fichiers en chasse fixe.
- Mouvement discret (150–200 ms) ; la progression anime sa valeur, rien de décoratif.
- **À éviter** : univers « logiciel audio » surchargé (potards, VU-mètres, néons), dégradés flashy, emojis, jargon technique en première ligne, alertes rouges agressives.
- Proposer **2 à 3 directions réellement différentes** (par exemple : A « papier » très épuré et clair ; B « studio » sobre, plus sombre et dense ; C « guidé » avec davantage d'illustrations légères et de pédagogie).

## 9. Critères de choix
1. Un nouvel utilisateur comprend **en 5 secondes** ce que fait l'écran et quoi cliquer.
2. L'étape ② est lisible **sans jargon** et fait apparaître clairement le **gain** et les **limites**.
3. Le **bouton Arrêter** est évident dans tous les états de progression.
4. Lisible en **clair et en sombre** ; tient à 900 × 620.
5. Réalisable en HTML/CSS simple, avec peu de jetons.

## 10. Livrables attendus et retour
- Les écrans A1 à H (§5) pour chaque direction, en clair et en sombre.
- Pour la direction retenue, la **liste des jetons CSS** nommés avec le préfixe `--pr-` :
  couleurs (`--pr-bg`, `--pr-surface`, `--pr-text`, `--pr-text-muted`, `--pr-border`, `--pr-accent`, `--pr-accent-text`, `--pr-ok`, `--pr-warn`, `--pr-error`, `--pr-neutral`), rayons (`--pr-radius-s/m/l`), espacements (`--pr-space-1…6`, grille de 8 px), ombres (`--pr-shadow-1/2`), typographie (`--pr-font-ui`, `--pr-font-mono`, 5 tailles `--pr-text-xs…xl`, interlignages), durées (`--pr-dur-fast/normal`), et leurs valeurs en clair et en sombre.
- L'inventaire des composants (§5) avec leurs états.
- Un court texte « pourquoi cette direction » (3 phrases).

**Ce que l'équipe fera ensuite** : choisir une direction, convertir les jetons en `tokens.css`, implémenter l'interface (`src/reable/app/static/`) et la vérifier dans un navigateur (clair, sombre, étroit, clavier).
