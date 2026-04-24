DATA = [
    (0.4, 0.50930, 0.003693),
    (0.5, 0.57380, 0.004717),
    (0.6, 0.63830, 0.005740),
    (0.7, 0.83110, 0.007595),
    (0.8, 1.02390, 0.009450),
    (0.9, 1.22125, 0.013057),
    (1.0, 1.41860, 0.016663),
    (1.1, 1.57467, 0.024827),
    (1.2, 1.74585, 0.033785),
    (1.3, 2.50854, 0.035222),
    (1.4, 3.44794, 0.036029)
]

def compute(u_input, c_input):  # tension du pot, cadence 
    """Calcule a0*c + a1*c^2 avec interpolation des coefficients."""
    if u_input <= 0.4:
        idx_low, idx_high, ratio = 0, 0, 0
    elif u_input >= 1.4:
        idx_low, idx_high, ratio = 10, 10, 0
    else:
        float_idx = (u_input - 0.4) / 0.1
        idx_low = int(float_idx)
        idx_high = idx_low + 1
        ratio = float_idx - idx_low

    # Extraction des coefficients
    _, a0_l, a1_l = DATA[idx_low]
    _, a0_h, a1_h = DATA[idx_high]
    
    # Interpolation des coefficients
    a0 = a0_l + (a0_h - a0_l) * ratio
    a1 = a1_l + (a1_h - a1_l) * ratio
    
    return a0 * c_input + a1 * (c_input ** 2)*0.8
