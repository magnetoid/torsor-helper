"""`python -m torsor_helper` — the same entry point as the `torsor` script.

Useful when the console script is not on PATH: inside a container, a CI step
that only has the interpreter, or a venv the shell has not activated.
"""
from torsor_helper.cli import main

if __name__ == "__main__":
    main()
