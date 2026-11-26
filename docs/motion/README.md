# A reply goes missing

1. The clerk's first issuance has committed. The reply disappears on its way back.
2. The generated recovery controller reads revision 2 and learns there is one issued ticket and two held.
3. The clerk's policy admits the remaining issuances. At revision 4, all three tickets have been issued and the controller returns `DONE`.

The numbered stubs stand for internal seat units. The frames follow the lost-reply case in the native demo. [Static storyboard](overview.png) · [Recovery demo](../RECOVERY.md)

Regenerate with Python, Pillow, fontconfig, Noto Serif Display and Liberation Sans.

```sh
python3 docs/motion/render.py
```

The command writes the GIF and the static PNG beside the renderer.
