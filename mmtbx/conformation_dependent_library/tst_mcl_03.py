from __future__ import absolute_import, division, print_function
import os
from libtbx import easy_run

pdb_string = '''
CRYST1  111.035  111.035  103.765  90.00  90.00  90.00 P 42 21 2
SCALE1      0.009006  0.000000  0.000000        0.00000
SCALE2      0.000000  0.009006  0.000000        0.00000
SCALE3      0.000000  0.000000  0.009637        0.00000
ATOM      1  CG  HIS A  94       4.447  42.151  13.943  0.77 17.81           C
ATOM      2  ND1 HIS A  94       5.032  40.915  13.774  0.73 17.16           N
ATOM      3  CD2 HIS A  94       4.981  42.659  15.076  0.74 17.98           C
ATOM      4  CE1 HIS A  94       5.861  40.696  14.786  0.74 16.72           C
ATOM      5  NE2 HIS A  94       5.842  41.736  15.605  0.77 17.63           N
ATOM      6  HD1 HIS A  94       4.884  40.375  13.121  0.80 20.60           H
ATOM      7  HD2 HIS A  94       4.794  43.496  15.436  1.00 21.59           H
ATOM      8  HE1 HIS A  94       6.375  39.930  14.902  1.00 20.08           H
ATOM      9  C   GLU A  95       2.025  43.133  17.485  0.67 19.15           C
ATOM     10  O   GLU A  95       2.858  42.410  18.055  0.71 20.41           O
ATOM     11  N   PHE A  96       2.183  44.438  17.387  0.71 19.57           N
ATOM     12  CA  PHE A  96       3.407  45.155  17.764  0.71 20.32           C
ATOM     13  C   PHE A  96       3.295  45.550  19.225  0.74 20.62           C
ATOM     14  CD1 PHE A  96       6.139  46.430  16.838  0.81 22.37           C
ATOM     15  CE1 PHE A  96       7.333  47.130  16.925  0.71 22.35           C
ATOM     16  HA  PHE A  96       4.182  44.577  17.687  1.00 24.39           H
ATOM     17  HD1 PHE A  96       6.161  45.512  16.690  1.00 26.85           H
ATOM     18  HE1 PHE A  96       8.139  46.677  16.825  1.00 26.83           H
ATOM     19  N   LYS A  97       3.603  44.608  20.107  0.77 20.43           N
ATOM     20  CA  LYS A  97       3.415  44.727  21.542  0.72 20.44           C
ATOM     21  C   LYS A  97       4.641  44.097  22.190  0.78 20.27           C
ATOM     22  O   LYS A  97       4.610  42.973  22.721  0.74 20.47           O
ATOM     23  H   LYS A  97       3.940  43.850  19.882  1.00 24.53           H
ATOM     24  HA  LYS A  97       3.377  45.661  21.803  1.00 24.54           H
ATOM     25  HB2 LYS A  97       2.092  43.190  21.621  1.00 25.53           H
ATOM     26  N   CYS A  98       5.742  44.842  22.169  0.68 19.66           N
ATOM     27  CA  CYS A  98       7.031  44.270  22.542  0.67 19.58           C
ATOM     28  O   CYS A  98       7.973  43.190  24.445  0.77 21.13           O
ATOM     29  CB  CYS A  98       8.182  45.122  22.026  0.60 19.62           C
ATOM     30  SG  CYS A  98       8.101  45.543  20.265  0.76 20.50           S
ATOM     31  H   CYS A  98       5.771  45.672  21.946  1.00 23.60           H
ATOM     32  HA  CYS A  98       7.094  43.403  22.111  1.00 23.51           H
ATOM     33  HB2 CYS A  98       8.193  45.954  22.523  1.00 23.55           H
ATOM     34  HB3 CYS A  98       9.009  44.637  22.171  0.93 23.55           H
ATOM     35  CA  CYS A 101       7.161  39.577  23.994  0.62 17.59           C
ATOM     36  CB  CYS A 101       7.310  40.364  22.701  0.65 17.76           C
ATOM     37  SG  CYS A 101       7.640  39.283  21.296  0.72 18.31           S
ATOM     38  HA  CYS A 101       6.486  38.892  23.868  1.00 21.12           H
ATOM     39  HB2 CYS A 101       6.488  40.849  22.525  1.00 21.32           H
ATOM     40  HB3 CYS A 101       8.049  40.985  22.788  1.00 21.32           H
ATOM     41  N   ARG A 103      10.777  37.930  22.421  0.66 17.18           N
ATOM     42  CA  ARG A 103      11.924  38.373  21.621  0.72 17.68           C
ATOM     43  C   ARG A 103      12.256  39.854  21.815  0.73 17.82           C
ATOM     44  O   ARG A 103      13.074  40.388  21.068  0.76 19.13           O
ATOM     45  CB  ARG A 103      11.725  38.036  20.147  0.73 18.00           C
ATOM     46  H   ARG A 103      10.036  38.305  22.200  1.00 20.63           H
ATOM     47  HB2 ARG A 103      10.867  38.386  19.860  1.00 21.62           H
ATOM     48  HB3 ARG A 103      12.439  38.448  19.634  1.00 21.62           H
ATOM     49  N   ARG A 104      11.684  40.513  22.818  0.73 18.25           N
ATOM     50  CA  ARG A 104      11.837  41.939  23.001  0.71 19.44           C
ATOM     51  C   ARG A 104      13.290  42.386  22.948  0.79 20.04           C
ATOM     52  O   ARG A 104      13.564  43.489  22.450  0.74 21.77           O
ATOM     53  CB  ARG A 104      11.180  42.351  24.315  0.65 20.65           C
ATOM     54  H   ARG A 104      11.191  40.146  23.419  1.00 21.92           H
ATOM     55  HA  ARG A 104      11.387  42.396  22.274  1.00 23.33           H
ATOM     56  HB2 ARG A 104      10.224  42.216  24.216  1.00 24.79           H
ATOM     57  HG3 ARG A 104      10.929  44.363  24.199  1.00 26.63           H
ATOM     58  CA  CYS A 107      14.141  40.912  17.640  0.74 16.49           C
ATOM     59  CB  CYS A 107      12.803  41.522  18.025  0.67 16.85           C
ATOM     60  SG  CYS A 107      11.577  41.287  16.684  0.72 16.87           S
ATOM     61  HA  CYS A 107      14.061  39.968  17.432  1.00 19.80           H
ATOM     62  HB2 CYS A 107      12.470  41.091  18.828  1.00 20.23           H
ATOM     63  HB3 CYS A 107      12.913  42.473  18.181  1.00 20.23           H
ATOM     64  CA  PHE A 109      11.822  43.112  13.160  0.70 16.48           C
ATOM     65  C   PHE A 109      11.778  44.447  13.912  0.71 16.79           C
ATOM     66  CB  PHE A 109      10.477  42.411  13.152  0.76 17.33           C
ATOM     67  CG  PHE A 109       9.396  43.177  12.443  0.75 17.14           C
ATOM     68  CD2 PHE A 109       8.246  43.568  13.102  0.74 18.13           C
ATOM     69  CE2 PHE A 109       7.222  44.234  12.410  0.74 18.70           C
ATOM     70  H   PHE A 109      12.563  41.592  14.165  1.00 19.86           H
ATOM     71  HB3 PHE A 109      10.190  42.276  14.069  1.00 20.81           H
ATOM     72  HD2 PHE A 109       8.150  43.389  14.009  1.00 21.76           H
ATOM     73  HE2 PHE A 109       6.431  44.453  12.848  1.00 22.46           H
ATOM     74  N   LEU A 110      11.819  44.413  15.247  0.72 17.76           N
ATOM     75  CA  LEU A 110      11.851  45.667  16.003  0.78 18.06           C
ATOM     76  CB  LEU A 110      11.929  45.370  17.496  0.74 18.64           C
ATOM     77  CG  LEU A 110      12.054  46.598  18.401  0.76 19.61           C
ATOM     78  CD1 LEU A 110      10.914  47.577  18.191  0.61 19.05           C
ATOM     79  CD2 LEU A 110      12.114  46.135  19.824  0.68 20.47           C
ATOM     80  H   LEU A 110      11.830  43.699  15.727  1.00 21.32           H
ATOM     81  HA  LEU A 110      11.032  46.164  15.853  1.00 21.69           H
ATOM     82  HB2 LEU A 110      11.122  44.899  17.756  1.00 22.38           H
ATOM     83  HB3 LEU A 110      12.706  44.812  17.656  1.00 22.38           H
ATOM     84 HD13 LEU A 110      10.071  47.104  18.279  1.00 22.87           H
ATOM     85 HD22 LEU A 110      11.317  45.621  20.024  1.00 24.58           H
ATOM     86 HD23 LEU A 110      12.903  45.582  19.943  1.00 24.58           H
ATOM     87 HG21 VAL A 113       8.468  47.188  13.530  1.00 22.60           H
ATOM     88  CB  LYS A 146       4.922  37.238  16.068  0.63 16.22           C
ATOM     89  CG  LYS A 146       4.385  37.431  17.504  0.55 15.69           C
ATOM     90  CD  LYS A 146       4.168  38.856  17.880  0.56 17.24           C
ATOM     91  CE  LYS A 146       3.869  38.984  19.365  0.63 18.84           C
ATOM     92  NZ  LYS A 146       3.526  40.252  19.782  0.48 19.13           N
ATOM     93  HA  LYS A 146       3.917  38.713  15.052  1.00 19.83           H
ATOM     94  HB3 LYS A 146       5.761  37.720  15.999  1.00 19.48           H
ATOM     95  HG3 LYS A 146       5.024  37.055  18.129  1.00 18.84           H
ATOM     96  HD2 LYS A 146       4.968  39.368  17.682  1.00 20.70           H
ATOM     97  HD3 LYS A 146       3.415  39.211  17.383  1.00 20.70           H
ATOM     98  HE2 LYS A 146       3.128  38.397  19.581  0.49 22.62           H
ATOM     99  HE3 LYS A 146       4.659  38.719  19.862  1.00 22.62           H
ATOM    100  HZ1 LYS A 146       2.809  40.535  19.337  1.00 22.96           H
ATOM    101  HZ2 LYS A 146       3.343  40.246  20.653  1.00 22.96           H
ATOM    102  HZ3 LYS A 146       4.200  40.814  19.632  1.00 22.96           H
ATOM    103  CA  VAL A 202      10.548  37.321  15.536  0.69 15.15           C
ATOM    104  C   VAL A 202      10.068  36.258  16.517  0.71 15.90           C
ATOM    105  CB  VAL A 202       9.385  37.927  14.733  0.65 14.91           C
ATOM    106  CG1 VAL A 202       9.864  39.187  13.988  0.68 16.53           C
ATOM    107  CG2 VAL A 202       8.776  36.926  13.790  0.63 15.08           C
ATOM    108  HA  VAL A 202      10.956  38.035  16.051  1.00 18.20           H
ATOM    109  HB  VAL A 202       8.681  38.185  15.349  1.00 17.90           H
ATOM    110 HG11 VAL A 202       9.123  39.557  13.484  1.00 19.84           H
ATOM    111 HG12 VAL A 202      10.180  39.836  14.636  1.00 19.84           H
ATOM    112 HG13 VAL A 202      10.584  38.943  13.386  1.00 19.84           H
ATOM    113 HG21 VAL A 202       8.044  37.346  13.312  1.00 18.10           H
ATOM    114 HG23 VAL A 202       8.447  36.170  14.301  1.00 18.10           H
ATOM    115  N   ALA A 203       9.030  36.578  17.292  0.72 15.95           N
ATOM    116  CA  ALA A 203       8.509  35.669  18.316  0.64 15.23           C
ATOM    117  CB  ALA A 203       8.039  36.486  19.524  0.52 14.58           C
ATOM    118  H   ALA A 203       8.606  37.324  17.242  1.00 19.15           H
ATOM    119  HB1 ALA A 203       7.701  35.881  20.202  1.00 17.51           H
ATOM    120  HB2 ALA A 203       8.790  36.990  19.876  1.00 17.51           H
ATOM    121  HB3 ALA A 203       7.337  37.093  19.242  1.00 17.51           H
TER
HETATM  122  S1  SF4 A 605       6.161  42.357  19.418  0.72 18.36           S
HETATM  123  S2  SF4 A 605       8.515  43.542  16.879  0.72 17.81           S
HETATM  124  S3  SF4 A 605       9.700  42.134  20.034  0.73 18.33           S
HETATM  125  S4  SF4 A 605       8.153  39.962  17.476  0.75 17.07           S
HETATM  126 FE1  SF4 A 605       9.599  41.722  17.775  0.72 17.00          Fe
HETATM  127 FE2  SF4 A 605       7.863  40.820  19.591  0.72 17.44          Fe
HETATM  128 FE3  SF4 A 605       6.948  41.912  17.304  0.74 17.32          Fe
HETATM  129 FE4  SF4 A 605       8.114  43.542  19.144  0.73 18.33          Fe
END
'''

def main():
  with open('tst_mcl_03.pdb', 'w') as f:
    f.write(pdb_string)
  cmd = 'phenix.pdb_interpretation tst_mcl_03.pdb write_geo=1'
  print (cmd)
  rc = easy_run.go(cmd)
  assert os.path.exists('tst_mcl_03.pdb.geo')
  return rc.return_code

if __name__ == '__main__':
  rc = main()
  assert not rc
  print('OK')
