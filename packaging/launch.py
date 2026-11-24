# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Entry point of the packaged application: GUI, or the CLI when given ``run``."""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "-h", "--help"):
        from openfemconex.cli import main
        sys.exit(main(sys.argv[1:]))
    from openfemconex.gui.main import main
    sys.exit(main())
