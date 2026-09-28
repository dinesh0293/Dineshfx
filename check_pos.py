import MetaTrader5 as mt5
import pandas as pd
import datetime

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

positions = mt5.positions_get(symbol="XAUUSD")
if positions is None or len(positions) == 0:
    positions = mt5.positions_get(symbol="XAUUSD+")

if positions:
    for p in positions:
        ptype = "BUY" if p.type == 0 else "SELL"
        print(f"OPEN POSITION: Ticket={p.ticket}, Type={ptype}, Volume={p.volume}, OpenPrice={p.price_open}, CurrentPrice={p.price_current}, SL={p.sl}, TP={p.tp}, Profit=${p.profit:.2f}, Comment={p.comment}")
else:
    print("No open positions")

from_date = datetime.datetime.now() - datetime.timedelta(days=2)
orders = mt5.history_orders_get(from_date, datetime.datetime.now())
if orders:
    print("\nRECENT ORDERS:")
    for o in orders:
        otype = "BUY" if o.type == 0 else "SELL"
        t_setup = datetime.datetime.fromtimestamp(o.time_setup)
        print(f"Order #{o.ticket} {otype} Vol={o.volume_initial} Price={o.price_open} SL={o.sl} TP={o.tp} Time={t_setup} State={o.state} Comment={o.comment}")

mt5.shutdown()
