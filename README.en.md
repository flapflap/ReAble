# ReAble

[Français](README.md) · **English**

**Your Ableton Live projects show missing plugins? ReAble finds them and swaps them in.**

A plugin was uninstalled, now exists only as VST3, or moved to a newer version (Massive as AU, Kontakt 5, Ozone 9…): Live shows it in red and the sound is gone. ReAble scans your projects, spots those plugins, and writes a **copy** of the project with the matching plugin, keeping the preset, settings and automations whenever it can.

> ⚠️ **Beta (0.1).** Your original projects are never modified (ReAble only writes copies), but **check every conversion in Live 12** before relying on it. Only plugins that have already been tested are converted; the others are reported. Apple Silicon Macs only for now. The app interface is currently in French.

## Install
1. Download **[ReAble.dmg](https://github.com/flapflap/ReAble/releases/tag/latest)**.
2. Open it and drag ReAble into the Applications folder.
3. Launch ReAble from Applications.

## Use it
The app follows three steps, shown on the left of the window.

**1 · Choisir (Choose)** — Drop a folder of projects on the window (or click “Choisir…”), then “Analyser” (Analyze). ReAble reads every project in the folder without changing anything.

**2 · Valider (Review)** — ReAble lists what it is going to do, conversion by conversion (“Kontakt 5 → Kontakt 8”, “Ozone 9 → Ozone 10”…). Tick the ones you want, adjust the options if needed (duplicate the original track, track names, where to write the copies), then:
- **Essai à blanc** (dry run) to see what would happen without writing anything;
- **Convertir** (Convert) to write the copies.

**3 · Convertir (Convert)** — Progress is shown live. You can **stop at any time**: what is already done is kept, and “Reprendre” (Resume) continues later. When it finishes, open the `… [ReAble].als` copies in Live: those are the ones to check. Not happy? **Annuler** (Undo) moves the copies to the Trash.

### What about plugins ReAble can't convert?
- The **Plugins manquants** (missing plugins) button shows, for each plugin, which projects use it and what to do.
- **Choisir un remplaçant** (choose a replacement): pick another plugin to use instead (a renamed plugin, or a different one that does the same job). The replacement starts with its default settings, and the old preset's name is written on the track.
- **Demander la prise en charge** (request support) opens a pre-filled request so the plugin gets added.
- In the **Plugins** tab you can **test** a plugin that isn't validated yet: ReAble writes a test copy, you open it in Live and answer “identical” or “problem”.

## Send feedback
Your feedback matters, especially during the beta!
- **From the app**: menu **ReAble > À propos de ReAble** (or the version number at the bottom left), then “Signaler un problème” (report a problem) or “Proposer une idée” (suggest an idea). The request opens on GitHub, already filled with your ReAble and macOS versions.
- **On GitHub**: [open an issue](https://github.com/flapflap/ReAble/issues/new/choose) (a free GitHub account is enough): problem, idea, or plugin to support. English is welcome.
- **For a problem**, tell us what you were doing, what you expected, what happened, and which plugin. A screenshot helps a lot. There is no need to send your projects.
- **Beta program** (Réglages / Settings): share your plugin test results anonymously to help validate more plugins.

## Your data
Everything happens on your Mac. Nothing is sent unless you ask for it. Original projects are never modified.

## For developers
Install from source, commands and architecture: [docs/DEVELOPPEMENT.md](docs/DEVELOPPEMENT.md) (French). Validated conversions live in [ReAble-library](https://github.com/flapflap/ReAble-library).

## License
[MIT](LICENSE). Ableton and Ableton Live are trademarks of Ableton AG; this project is neither affiliated with nor endorsed by Ableton.
