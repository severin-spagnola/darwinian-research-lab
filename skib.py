import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

# Your data
data = """time,voltage,current_mA
0.00,-0.008,0.449
0.05,-0.008,0.449
0.10,-0.007,0.470
0.15,-0.007,0.470
0.20,-0.007,0.470
0.25,-0.008,0.470
0.30,0.002,0.490
0.35,0.006,0.489
0.40,0.005,0.490
0.45,0.013,0.510
0.50,0.017,0.530
0.55,0.016,0.531
0.60,0.018,0.551
0.65,0.026,0.571
0.70,0.028,0.592
0.75,0.027,0.591
0.80,0.035,0.612
0.85,0.037,0.631
0.90,0.040,0.632
0.95,0.046,0.652
1.00,0.046,0.673
1.05,0.045,0.673
1.10,0.049,0.693
1.15,0.048,0.692
1.20,0.046,0.713
1.25,0.054,0.733
1.30,0.059,0.753
1.35,0.059,0.774
1.40,0.070,0.794
1.45,0.069,0.794
1.50,0.068,0.814
1.55,0.070,0.833
1.60,0.077,0.854
1.65,0.076,0.853
1.70,0.076,0.874
1.75,0.082,0.894
1.80,0.087,0.914
1.85,0.087,0.914
1.90,0.088,0.934
1.95,0.087,0.934
2.00,0.093,0.955
2.05,0.095,0.975
2.10,0.096,0.975
2.15,0.104,0.995
2.20,0.106,1.016
2.25,0.107,1.036
2.30,0.118,1.056
2.35,0.118,1.056
2.40,0.118,1.077
2.45,0.119,1.096
2.50,0.121,1.117
2.55,0.117,1.116
2.60,0.126,1.137
2.65,0.129,1.157
2.70,0.131,1.178
2.75,0.139,1.197
2.80,0.140,1.218
2.85,0.138,1.217
2.90,0.141,1.218
2.95,0.149,1.238
3.00,0.150,1.258
3.05,0.155,1.258
3.10,0.159,1.279
3.15,0.157,1.278
3.20,0.158,1.299
3.25,0.157,1.318
3.30,0.167,1.339
3.35,0.167,1.339
3.40,0.166,1.339
3.45,0.169,1.359
3.50,0.177,1.379
3.55,0.175,1.378
3.60,0.177,1.399
3.65,0.181,1.419
3.70,0.187,1.439
3.75,0.187,1.440
3.80,0.186,1.439
3.85,0.194,1.459
3.90,0.197,1.479
3.95,0.197,1.479
4.00,0.197,1.500
4.05,0.201,1.520
4.10,0.204,1.540
4.15,0.206,1.540
4.20,0.216,1.560
4.25,0.215,1.560
4.30,0.217,1.580
4.35,0.222,1.600
4.40,0.224,1.621
4.45,0.223,1.621
4.50,0.224,1.641
4.55,0.233,1.660
4.60,0.234,1.681
4.65,0.238,1.701
4.70,0.244,1.721
4.75,0.249,1.741
4.80,0.253,1.762
4.85,0.254,1.781
4.90,0.255,1.801
4.95,0.254,1.822
5.00,0.262,1.842"""

# Parse the data
from io import StringIO
df = pd.read_csv(StringIO(data))

# Extract current and voltage
current_mA = df['current_mA'].values
voltage = df['voltage'].values

print("="*70)
print("OHMS LAW EXPERIMENT - DATA ANALYSIS")
print("="*70)
print(f"\nNumber of data points: {len(current_mA)}")
print(f"Current range: {current_mA.min():.3f} to {current_mA.max():.3f} mA")
print(f"Voltage range: {voltage.min():.3f} to {voltage.max():.3f} V")

# Perform linear regression
slope, intercept, r_value, p_value, std_err = stats.linregress(current_mA, voltage)

print("\n" + "="*70)
print("LINEAR REGRESSION RESULTS (V vs mA)")
print("="*70)
print(f"Slope: {slope:.6f} V/mA")
print(f"Standard Error of Slope: {std_err:.6f} V/mA")
print(f"Intercept: {intercept:.6f} V")
print(f"R-squared: {r_value**2:.8f}")
print(f"P-value: {p_value:.2e}")

# Convert to Ohms
R_measured = slope * 1000  # V/mA to V/A (Ohms)
R_uncertainty = std_err * 1000  # Convert uncertainty too

print("\n" + "="*70)
print("RESISTANCE FROM V-I SLOPE (converted to Ohms)")
print("="*70)
print(f"Resistance (raw): {R_measured:.4f} Ω")
print(f"Uncertainty (raw): {R_uncertainty:.4f} Ω")

# Apply rounding rules from lab manual
# Rule 1: Round uncertainty to 1 significant figure
def round_to_n_sig_figs(x, n):
    if x == 0:
        return 0
    from math import log10, floor
    return round(x, -int(floor(log10(abs(x)))) + (n - 1))

R_uncertainty_rounded = round_to_n_sig_figs(R_uncertainty, 1)

# Rule 2: Round result to same decimal places as uncertainty
if R_uncertainty_rounded >= 1:
    # Round to integer
    R_measured_rounded = round(R_measured)
    decimal_places = 0
else:
    # Determine decimal places from uncertainty
    from math import log10, floor
    decimal_places = -int(floor(log10(abs(R_uncertainty_rounded))))
    R_measured_rounded = round(R_measured, decimal_places)

print("\n" + "="*70)
print("PROPERLY ROUNDED VALUES (following lab manual rules)")
print("="*70)
print(f"Resistance: {R_measured_rounded} ± {R_uncertainty_rounded} Ω")

# Multimeter measurement
R_multimeter = 219.7
R_multimeter_uncertainty = 0.1

print("\n" + "="*70)
print("COMPARISON WITH MULTIMETER")
print("="*70)
print(f"Multimeter: {R_multimeter} ± {R_multimeter_uncertainty} Ω")
print(f"V-I Method: {R_measured_rounded} ± {R_uncertainty_rounded} Ω")

# Check if they agree
difference = abs(R_measured_rounded - R_multimeter)
combined_uncertainty = R_uncertainty_rounded + R_multimeter_uncertainty

print(f"\nDifference: {difference:.1f} Ω")
print(f"Combined uncertainties: {combined_uncertainty:.1f} Ω")

if difference <= combined_uncertainty:
    print("\n✓ VALUES AGREE within experimental uncertainty")
    agreement = "agreement"
else:
    print("\n✗ VALUES DO NOT AGREE within experimental uncertainty")
    percent_diff = (difference / R_multimeter) * 100
    print(f"Percent difference: {percent_diff:.1f}%")
    agreement = "disagreement"

# Create the plot
plt.figure(figsize=(10, 7))
plt.scatter(current_mA, voltage, s=50, alpha=0.7, color='black', label='Data', zorder=3)

# Plot the fit line
current_fit = np.linspace(current_mA.min(), current_mA.max(), 100)
voltage_fit = slope * current_fit + intercept
plt.plot(current_fit, voltage_fit, 'r-', linewidth=2, 
         label=f'Linear fit: $y = {slope:.2f}x - {abs(intercept):.2f} \\times 10^{{-2}}$',
         zorder=2)

plt.xlabel('Current (mA)', fontsize=14)
plt.ylabel('Voltage (V)', fontsize=14)
plt.title('Voltage vs Current - Verification of Ohm\'s Law', fontsize=16)
plt.grid(True, alpha=0.3, zorder=1)
plt.legend(fontsize=12, loc='upper left')
plt.tight_layout()

# Save the figure
plt.savefig('vi_plot.png', dpi=300, bbox_inches='tight')
print("\n" + "="*70)
print(f"Plot saved as 'vi_plot.png'")
print("="*70)

plt.show()

# Summary for LaTeX document
print("\n" + "="*70)
print("VALUES TO INSERT IN YOUR LATEX DOCUMENT:")
print("="*70)
print(f"\nSlope (for Results section):")
print(f"  {R_measured_rounded} ± {R_uncertainty_rounded} Ω")
print(f"\nMultimeter (for Results section):")
print(f"  {R_multimeter} ± {R_multimeter_uncertainty} Ω")
print(f"\nAgreement status (for Abstract):")
print(f"  {agreement}")
if agreement == "disagreement":
    print(f"\nPercent difference (for Results section):")
    print(f"  {percent_diff:.1f}%")
print("\n" + "="*70)