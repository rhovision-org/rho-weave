# Motion graphics

The overview is an illustrative, locally generated looping GIF, not live data. [Static version](overview.png).

To regenerate, install Pillow in an isolated Python environment and run:

```sh
python docs/motion/render.py weave docs/motion /path/to/font-directory
```

The font directory must contain Roboto-Regular.ttf or DejaVuSans.ttf. No font files are bundled. The diagrams are not part of the product runtime or CI.
