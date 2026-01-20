# Update Summary (Li2023 calibration)

Date: 20 Jan 2026

## Scope
- Calibrated inherent-strain law for four Li2023 benchmark cases (1, 6, 87, 90).
- Added pass-dependent energy scaling and localized low-energy single-pass correction.
- Preserved output tagging for reproducible runs.

## Key model updates
- Pass scaling (multi-pass): energy-dependent attenuation at high energy and low-energy attenuation for multi-pass.
- Single-pass boost: linear high-energy boost for single-pass.
- Low-energy single-pass Gaussian boost to lift case 1 without disturbing multi-pass and high-energy cases.

## Final calibrated parameters
- Base law: `C=0.06`, `a=0.35`, `b=0.0`, `p=0.325`
- Pass scaling: `delta=0.02`, `k_energy=0.43`, `k_low=0.88`, `e_ref_pass=800`
- Single-pass boost: `k_single=0.33`
- Low-energy single-pass boost: `eta_low_single=0.2`, `e0_low_single=600`, `de_low_single=180`

## Latest results
- Summary CSV: [results/li2023_comparison_v8_full_four_cases_lowE_single.csv](results/li2023_comparison_v8_full_four_cases_lowE_single.csv)
- Case outputs:
  - [results/li2023_case_001_v8_full_four_cases_lowE_single/report.pdf](results/li2023_case_001_v8_full_four_cases_lowE_single/report.pdf)
  - [results/li2023_case_006_v8_full_four_cases_lowE_single/report.pdf](results/li2023_case_006_v8_full_four_cases_lowE_single/report.pdf)
  - [results/li2023_case_087_v8_full_four_cases_lowE_single/report.pdf](results/li2023_case_087_v8_full_four_cases_lowE_single/report.pdf)
  - [results/li2023_case_090_v8_full_four_cases_lowE_single/report.pdf](results/li2023_case_090_v8_full_four_cases_lowE_single/report.pdf)

## Files updated
- Core calibration logic: [scripts/run_li2023_cases.py](scripts/run_li2023_cases.py)

## Notes
- The final tag is set to `final_calibrated` in [scripts/run_li2023_cases.py](scripts/run_li2023_cases.py).
- Use the comparison CSV above as the authoritative summary of the calibrated fit.
