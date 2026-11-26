# Motion graphics

An illustrated example, not live telemetry. [Static image](overview.png).

Regenerate with Python and Pillow in an isolated environment:

```sh
python docs/motion/render.py weave docs/motion /path/to/font-directory
```

Fonts are selected from Roboto or DejaVu families, with serif and monospace alternatives when available. No font files are distributed. The animation generator is optional documentation tooling, not a product dependency.
