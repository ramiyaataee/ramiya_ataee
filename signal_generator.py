def generate_signal(df):
    if df["EMA9"].iloc[-2] < df["EMA21"].iloc[-2] and df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "BUY"
    elif df["EMA9"].iloc[-2] > df["EMA21"].iloc[-2] and df["EMA9"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "SELL"
    else:
        return "HOLD"
