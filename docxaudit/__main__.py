"""`python -m docxaudit` runs the same command as the installed `docxaudit`."""
import sys

from .cli import main

sys.exit(main())
