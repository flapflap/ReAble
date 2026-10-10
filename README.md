# ReAble

**Vos projets Ableton Live ne s'ouvrent plus à cause de plugins manquants ? ReAble les retrouve et les remplace.**

Un plugin a été désinstallé, n'existe plus qu'en VST3, ou a changé de version (Massive en AU, Kontakt 5, Ozone 9…) : Live l'affiche en rouge et vous perdez le son. ReAble analyse vos projets, repère ces plugins et crée une **copie** du projet avec le plugin équivalent, en gardant autant que possible le preset, les réglages et les automations.

> ⚠️ **Version bêta (0.1).** Vos projets d'origine ne sont jamais modifiés (ReAble n'écrit que des copies), mais **vérifiez chaque conversion dans Live 12** avant de vous y fier. Seuls les plugins déjà testés sont convertis, les autres sont signalés. Mac Apple Silicon uniquement pour l'instant.

## Installer
1. Téléchargez **[ReAble.dmg](https://github.com/flapflap/ReAble/releases/tag/latest)**.
2. Ouvrez-le et glissez ReAble dans le dossier Applications.
3. Lancez ReAble depuis Applications.

## Utiliser
L'application suit trois étapes, indiquées à gauche de la fenêtre.

**1 · Choisir** — Glissez un dossier de projets sur la fenêtre (ou cliquez sur « Choisir… »), puis « Analyser ». ReAble lit tous les projets du dossier sans rien modifier.

**2 · Valider** — ReAble liste ce qu'il va faire, par conversion (« Kontakt 5 → Kontakt 8 », « Ozone 9 → Ozone 10 »…). Cochez ce que vous voulez convertir, réglez les options si besoin (dupliquer la piste d'origine, nom des pistes, où écrire les copies), puis :
- **Essai à blanc** pour voir ce qui se passerait, sans rien écrire ;
- **Convertir** pour écrire les copies.

**3 · Convertir** — La progression s'affiche en direct. Vous pouvez **arrêter à tout moment** : ce qui est fait est conservé, et « Reprendre » continue plus tard. À la fin, ouvrez les copies `… [ReAble].als` dans Live : ce sont elles qu'il faut vérifier. Un doute ? **Annuler** met les copies à la corbeille.

### Et pour les plugins que ReAble ne sait pas convertir ?
- Le bouton **Plugins manquants** donne, pour chaque plugin, les projets concernés et ce qu'il faut faire.
- **Choisir un remplaçant** : indiquez un autre plugin à mettre à la place (un plugin renommé, ou un autre qui fait le même travail). Le remplaçant démarre avec ses réglages par défaut, le nom de l'ancien preset est noté sur la piste.
- **Demander la prise en charge** ouvre une demande pré-remplie pour que le plugin soit ajouté.
- Dans l'onglet **Plugins**, vous pouvez **tester** un plugin pas encore validé : ReAble crée une copie de test, vous l'ouvrez dans Live et vous répondez « identique » ou « problème ».

## Faire un retour
Votre avis compte, surtout pendant la bêta !
- **Depuis l'application** : menu **ReAble > À propos de ReAble** (ou le numéro de version en bas à gauche), puis « Signaler un problème » ou « Proposer une idée ». La demande s'ouvre sur GitHub, déjà remplie avec votre version de ReAble et de macOS.
- **Sur GitHub** : [ouvrir une demande](https://github.com/flapflap/ReAble/issues/new/choose) (un compte GitHub gratuit suffit) : problème, idée, ou plugin à prendre en charge.
- **Pour un problème**, dites-nous : ce que vous faisiez, ce que vous attendiez, ce qui s'est passé, et le plugin concerné. Une capture d'écran aide beaucoup. Inutile d'envoyer vos projets.
- **Programme bêta** (Réglages) : partagez, de façon anonyme, le résultat de vos tests de plugins pour aider à en valider davantage.

## Vos données
Tout se passe sur votre Mac. Rien n'est envoyé sans que vous le demandiez. Les projets d'origine ne sont jamais modifiés.

## Pour les développeurs
Installation depuis les sources, commandes et architecture : [docs/DEVELOPPEMENT.md](docs/DEVELOPPEMENT.md). Les conversions validées sont dans [ReAble-library](https://github.com/flapflap/ReAble-library).

## Licence
[MIT](LICENSE). Ableton et Ableton Live sont des marques d'Ableton AG ; ce projet n'est ni affilié ni approuvé par Ableton.
