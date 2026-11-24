# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
import numpy as np
import pytest

from openfemconex.results import read_dat, read_frd, von_mises
from openfemconex.runner import _read_sta

DAT = """
 forces (fx,fy,fz) for set ANCHORGND and time  0.5000000E+00

        11  1.000000E+00  2.000000E+00 -3.000000E+00

 forces (fx,fy,fz) for set ANCHORGND and time  0.1000000E+01

        11  1.000000E+00  2.000000E+00 -6.000000E+00
        12  0.000000E+00  0.000000E+00  0.000000E+00

 total force (fx,fy,fz) for set CONCBOT and time  0.1000000E+01

        1.000000E-02  2.000000E-02  1.500000E+06
"""

FRD = """    1C
    1PSTEP                         1           1           1
  100CL  101 1.000000000           2                     0    1           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -1         1 1.00000E+00-2.00000E+00 3.00000E-01
 -1         2 0.00000E+00 0.00000E+00-1.00000E-10
 -3
 9999
"""

STA = """SUMMARY OF JOB INFORMATION
  STEP      INC     ATT  ITRS     TOT TIME     STEP TIME      INC TIME
     1          1     1     7  0.100000E+01  0.100000E+01  0.100000E+01
     2          1     1U   60  0.100000E+01  0.000000E+00  0.200000E+00
     2          1     2     5  0.105000E+01  0.500000E-01  0.500000E-01
"""


def test_read_dat_keeps_the_last_table(tmp_path):
    path = tmp_path / "a.dat"
    path.write_text(DAT)
    dat = read_dat(path)
    assert dat["forces/ANCHORGND"][11][2] == -6.0
    assert set(dat["forces/ANCHORGND"]) == {11, 12}
    assert dat["total force/CONCBOT"][0][2] == 1.5e6


def test_read_frd_fixed_width(tmp_path):
    path = tmp_path / "a.frd"
    path.write_text(FRD)
    ids, values = read_frd(path)["DISP"]
    assert list(ids) == [1, 2]
    assert values[0] == pytest.approx([1.0, -2.0, 0.3])
    assert values[1, 2] == pytest.approx(-1e-10)


def test_read_sta_ignores_failed_attempts(tmp_path):
    path = tmp_path / "a.sta"
    path.write_text(STA)
    assert _read_sta(path) == (2, 0.05, 2, 72)


def test_von_mises_uniaxial_and_shear():
    s = np.array([[100.0, 0, 0, 0, 0, 0], [0, 0, 0, 50.0, 0, 0]])
    assert von_mises(s) == pytest.approx([100.0, 50.0 * 3**0.5])
