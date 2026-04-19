import math

def calculate_rsrp(p_tx, distance_km, frequency_mhz):
    # Log-distance path loss
    return p_tx - 20 * math.log10(distance_km) - 32.4 - 20 * math.log10(frequency_mhz)
