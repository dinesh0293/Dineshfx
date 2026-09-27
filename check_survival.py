import MetaTrader5 as mt5
import pandas as pd
import numpy as np

from compare_lot_sizes import compare_lots

# Let's inspect the equity trajectory from Day 1 for 0.01 and 0.02 lot
def check_survival():
    import compare_lot_sizes
    # run and check minimum equity reached
