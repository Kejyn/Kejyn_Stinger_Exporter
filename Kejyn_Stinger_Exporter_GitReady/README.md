# Kejyn Stinger Exporter

Petit outil Windows pour prévisualiser une transition HTML/CSS/JS et l'exporter en **WebM VP9 transparent + audio Opus**, prêt pour les **Stinger Transitions OBS**.

## Fonctionnalités

- Sélection séparée du HTML, CSS et JavaScript.
- Son optionnel.
- Réglage du volume.
- Fade audio de fin.
- Prévisualisation Chromium.
- Export 1920×1080 / 60 FPS ou valeurs personnalisées.
- VP9 + canal alpha `yuva420p`.
- Installation Windows propre via **Inno Setup**.
- Chromium Playwright embarqué dans l'installation : l'utilisateur final n'a ni Python, ni Playwright, ni FFmpeg à installer.

## Utilisateur final

Une release GitHub contient simplement :

```text
KejynStingerExporter-Setup-1.0.0.exe
```

Il suffit de lancer l'installateur.

Installation par utilisateur dans :

```text
%LOCALAPPDATA%\Programs\Kejyn Stinger Exporter
```

Aucun droit administrateur n'est nécessaire.

L'installateur ajoute :
- l'application ;
- Chromium nécessaire au rendu ;
- FFmpeg fourni par `imageio-ffmpeg` ;
- le raccourci du menu Démarrer ;
- un raccourci Bureau optionnel ;
- un désinstalleur Windows standard.

## Développement

### Lancer depuis les sources

```bat
scripts\run_dev.bat
```

### Construire l'installateur localement

Pré-requis :
- Python 3.11+
- Inno Setup 6

Puis :

```bat
scripts\build_windows_installer.bat
```

Le script :
1. crée un environnement Python ;
2. installe les dépendances ;
3. télécharge Chromium ;
4. construit l'application avec PyInstaller ;
5. construit l'installateur Inno Setup.

Résultat :

```text
release\KejynStingerExporter-Setup-1.0.0.exe
```

## Releases GitHub automatiques

Le workflow :

```text
.github/workflows/windows-release.yml
```

construit automatiquement le `Setup.exe`.

Pour publier une version :

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions :
- compile l'application sur Windows ;
- embarque Chromium ;
- construit l'installateur ;
- ajoute automatiquement le `.exe` à la GitHub Release.

Le workflow peut aussi être lancé manuellement depuis l'onglet **Actions**.

## Format attendu d'une transition

Le JavaScript doit exposer :

```js
window.renderTransition = renderTransition;
```

avec :

```js
renderTransition(progress)
```

où `progress` va de `0` à `1`.

La transition KejynDev actuelle respecte déjà cette convention.

## Réglages conseillés pour la transition KejynDev

```text
Résolution : 1920 × 1080
FPS        : 60
Durée      : 1800 ms
Volume     : 65 %
Fade audio : 250 ms
CRF VP9    : 18
```

Pour OBS, le point de transition est autour de `900 ms`.
