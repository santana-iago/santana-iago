# Installation

## Publish the profile

1. Extract the archive.
2. Open the internal `santana-iago` directory.
3. Upload **all files and directories inside it** to the public GitHub repository named `santana-iago`.
4. Preserve the hidden `.github` directory.
5. Open **Actions → Build profile assets → Run workflow**.
6. Open **Actions → Generate profile summary cards → Run workflow**.

GitHub shows a profile README when a public repository has the same name as the account and contains a `README.md` in its root.

## Edit the profile

Edit `profile.yml`, not the generated SVG files or `README.md` directly. Then run:

```bash
python -m pip install -r requirements.txt
python scripts/test_build_profile.py
python scripts/build_profile.py
python scripts/validate_profile.py
```

The build generates:

- responsive desktop and mobile SVG sections;
- the root `README.md`;
- desktop and mobile PNG previews;
- `REPOSITORY-CONTENTS.txt`.

## Typography

The main statement uses a Georgia-style editorial serif. All remaining text uses a system UI stack: San Francisco on Apple devices, Segoe UI on Windows and Helvetica/Arial fallbacks elsewhere. No font files are included.

## Profile statistics

The statistics workflow generates the `github_dark` summary card under:

```text
profile-summary-card-output/github_dark/0-profile-details.svg
```

The placeholder remains visible until the workflow finishes successfully.

## Generated assets

The README references only `assets/generated/`. The build replaces this directory atomically, so there are no legacy version folders or hidden placeholder assets.


## Appearance

The `<img>` in each README `<picture>` points to the mobile SVG. A width-only source selects the desktop SVG on wide screens. Each SVG paints its own background and switches its palette and logo variants together using `prefers-color-scheme`. Clients that ignore the SVG theme query get the complete light palette, including the light background.
