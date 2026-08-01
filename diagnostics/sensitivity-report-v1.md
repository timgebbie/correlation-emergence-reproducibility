# Sensitivity and robustness report - v1.0.0

Artefact status: **diagnostic output**

Result: **16 verified; 0 failed**

| ID | Sensitivity check | Status | Observed |
|---|---|---:|---|
| S01 | Ordinary component product at kappa/lambda=0.25 | Verified | maximum product error=0.000e+00 |
| S02 | Ordinary component product at kappa/lambda=1 | Verified | maximum product error=0.000e+00 |
| S03 | Ordinary component product at kappa/lambda=4 | Verified | maximum product error=0.000e+00 |
| S04 | Aggregation-scale rate sensitivity | Verified | S(0.001)=0.999667; S(100)=0.010101 |
| S05 | Fractional short-scale exponent for (0.8, 0.8) | Verified | fitted slope=1.592159 |
| S06 | Fractional short-scale exponent for (0.6, 1.0) | Verified | fitted slope=1.587231 |
| S07 | Fractional short-scale exponent for (0.6, 0.6) | Verified | fitted slope=1.176871 |
| S08 | Equal-sum fractional-order confounding | Verified | slope difference=0.004929 |
| S09 | Boundary-rate elasticity for coupling_strength | Verified | fitted elasticity=1.000000000000 |
| S10 | Boundary-rate elasticity for source_amplitude | Verified | fitted elasticity=1.000000000000 |
| S11 | Boundary-rate elasticity for source_width | Verified | fitted elasticity=-0.500000000000 |
| S12 | Boundary-rate elasticity for front_slope_abs | Verified | fitted elasticity=-1.000000000000 |
| S13 | Centred full-domain selector invariance | Verified | maximum absolute deviation=1.221e-15 |
| S14 | Off-grid selector sensitivity | Verified | error range=[1.515e-09,1.032e-01] |
| S15 | Finite-domain truncation sensitivity | Verified | moment-ratio range=[0.804144,0.902396] |
| S16 | Future v2 overlay schema | Verified | missing fields=[] |

The robust conclusions are local sensitivity, equal-sum fractional confounding, conditional boundary-rate propagation, centred parity invariance, and bounded representation distortions under the declared grid profiles. None is an empirical calibration or a proof of unique parameter recovery.
