#!/usr/bin/python3.9
import lib_ohlc as o
import lib_globals as g
from colorama import init
init()

def get_pt1(ohlc, **kwargs):
    ax = kwargs['ax']
    # + * add the column
    ohlc['one_pt'] = 0

    def tfunc(dfline, **kwargs):
        df = kwargs['df']
        g.idx = dfline['ID']
        CLOSE = dfline['Close']
        OPEN = dfline['Open']
        g.pt1 = 0
        try:
            PCLOSE = df['Close'][g.idx - 1]
        except:
            PCLOSE = CLOSE

        if CLOSE > PCLOSE:
            g.pt1 = g.previous_point + 1
        if CLOSE < PCLOSE:
            g.pt1 = g.previous_point - 1

        g.previous_point = g.pt1
        return g.pt1

    ohlc['one_pt'] = ohlc.apply(lambda x: tfunc(x, df=ohlc, ax=ax), axis=1)

    ohlc['one_pt'] = ohlc['one_pt'].ewm(span=cvars.get("bb_ewm_length")["upper"], adjust=False).mean()

    ohlc['one_pt'] = normalize_col(ohlc['one_pt'], -0.5, 0.5)

    plot_pt1 = mpf.make_addplot(
        ohlc['one_pt'],
        ax=ax,
        type="line",
        color=cvars.get("pt1style")['color'],
        width=cvars.get("pt1style")['width'],
        alpha=1  # + cvars.get('tholostyle_I')['color'],
    )
    ax.axhline(y=0.0, color='black')
    ax.axhline(y=cvars.get("pt1_highlimit_sell"), color='cyan')
    ax.axhline(y=cvars.get("pt1_lowlimit_buy"), color='magenta')

    return [plot_pt1]





ohlc = o.get_ohlc(g.ticker_src, g.spot_src, since=t.since)