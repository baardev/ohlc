from lib_cvars import Cvars
import lib_globals as g
import lib_ohlc as o
# + cvars = Cvars(g.cfgfile)

class Tests:
    def __init__(self, cvars, dfl, df, **kwargs):
        # + self.cargs = cargs
        idx = kwargs['idx']
        self.df = df
        self.dfl = dfl
        self.cvars = cvars
        self.FLAG = True
        # + - RUNTIME VARS
        self.AVG_PRICE = g.avg_price

        # + - CONFIG VARS
        self.DELTAHIGH = cvars.get('delta_highlimit_buy')
        self.CLOSE_X_N = cvars.get('closeXn')

        # + * OHCLV
        self.OPEN = dfl['Open']
        self.HIGH = dfl['High']
        self.LOW =  dfl['Low']
        self.CLOSE = dfl['Close']
        self.PREV_CLOSE = df.iloc[idx-1]['Close']
        self.VOLUME = dfl['Volume']

        # + * BB lines abd avg
        self.BB3_UP_AVG = dfl['bbuAvg']
        self.BB3_LOW_AVG = dfl['bblAvg']
        self.BB3_MID_AVG = dfl['bbmAvg']


        self.BB_HIGH_1 = dfl['bbh0']
        self.BB_HIGH_2 = dfl['bbh1']
        self.BB_HIGH_3 = dfl['bbh2']
        self.BB_LOW_1 = dfl['bbl0']
        self.BB_LOW_2 = dfl['bbl1']
        self.BB_LOW_3 = dfl['bbl2']

        self.STEPSUP = dfl['stepsup'] if "stepsup" in df else False
        self.STEPSDN = dfl['stepsdn'] if "stepsdn" in df else False

        self.FFMAPS = dfl['ffmaps'] if "ffmaps" in df else False
        self.BBDELTA = dfl['bbDelta'] if "bbDelta" in df else False

        self.MAVLONG = dfl['MAV20'] if "MAV20" in df else False
        self.MAVLONGER = dfl['MAV40'] if "MAV40" in df else False
        self.MAVLONGEST = dfl['MAV60'] if "MAV60" in df else False

        self.LBLOW = dfl['lblow'] if "lblow" in df else False

        current_ffmaps = df.iloc[len(df.index)-1]['ffmaps']
        ffcp = df.iloc[len(df.index)-2]['ffmaps']
        ffcpp = df.iloc[len(df.index)-3]['ffmaps']

        self.FFMAPS_UPTURN = current_ffmaps > ffcp and ffcp < ffcpp
        self.FFMAPS_DNTURN = current_ffmaps < ffcp and ffcp > ffcpp



        if "ou-mid" in df:
            self.OU_MID = dfl['ou-mid']
            self.PREV_OU_MID = df.iloc[idx-1]['ou-mid']

        self.ONE_PT = dfl['one_pt'] if "one_pt" in df else False

        self.MACD = dfl['MACD'] if "MACD" in df else False
        self.SIGNAL = dfl['MACDSignalLine'] if "MACDSignalLine" in df else False
        self.HIST = dfl['Histogram'] if "Histogram" in df else False

        self.EMA12 = dfl['EMA12'] if "EMA12" in df else False
        self.EMA26 = dfl['EMA26'] if "EMA26" in df else False

        self.OPCLDELTA = dfl['opcldelta'] if "opcldelta" in df else False
        self.HILODELTA = dfl['hilodelta'] if "hilodelta" in df else False
        self.DELTADELTA = dfl['deltadelta'] if "deltadelta" in df else False

        self.FFMAPULIM =  dfl['ffmapulim'] if "ffmapulim" in df else False
        self.FFMAPLLIM =  dfl['ffmapllim'] if "ffmapllim" in df else False
        self.FFMAP =  dfl['ffmap'] if "ffmap" in df else False

        self.FFMAPULIM2 =  dfl['ffmapulim2'] if "ffmapulim2" in df else False
        self.FFMAPLLIM2 =  dfl['ffmapllim2'] if "ffmapllim2" in df else False
        self.FFMAP2 =  dfl['ffmap2'] if "ffmap2" in df else False

        self.LOWERCLOSE =  dfl['lowerClose'] if "lowerClose" in df else False
        self.AMP =  dfl['amp'] if "amp" in df else False

        self.SIGLF = dfl['siglf'] if "siglf" in df else False
        self.SIGFF = dfl['sigff'] if "sigff" in df else False
        # + self.SIGFF_LOW = dfl['sigff_low'] if "sigff_low" in df else False
        # + self.SIGFF_HI = dfl['sigff_hi'] if "sigff_hi" in df else False

        self.S = dfl['S'] if "S" in df else False
        self.V = dfl['V'] if "V" in df else False
        self.I = dfl['I'] if "I" in df else False
        self.R = dfl['R'] if "R" in df else False

        self.HICLIM = dfl['hilim'] if "hilim" in df else False
        self.LOCLIM = dfl['lolim'] if "lolim" in df else False

        # + * predefined macros
        self.CoA = self.CLOSE > self.AVG_PRICE

        # + * LOW is below all three BB low bands
        self.Lunder3BBlow = self.compare(price=self.LOW, type='lt', against=self.BB_LOW_1) and \
                            self.compare(price=self.LOW, type='lt', against=self.BB_LOW_2) and \
                            self.compare(price=self.LOW, type='lt', against=self.BB_LOW_3)
        # + * CLOSE is below all three BB low bands
        self.Cunder3BBlow = self.compare(price=self.CLOSE, type='lt', against=self.BB_LOW_1) and \
                            self.compare(price=self.CLOSE, type='lt', against=self.BB_LOW_2) and \
                            self.compare(price=self.CLOSE, type='lt', against=self.BB_LOW_3)
        # + * CLOSE is above all three BB high bands
        self.Cover3BBhigh = self.compare(price=self.CLOSE, type='gt', against=self.BB_HIGH_1) and \
                            self.compare(price=self.CLOSE, type='gt', against=self.BB_HIGH_2) and \
                            self.compare(price=self.CLOSE, type='gt', against=self.BB_HIGH_3)
        # + * HIGH is above all three BB high bands
        self.Hover3BBhigh = self.compare(price=self.HIGH, type='gt', against=self.BB_HIGH_1) and \
                            self.compare(price=self.HIGH, type='gt', against=self.BB_HIGH_2) and \
                            self.compare(price=self.HIGH, type='gt', against=self.BB_HIGH_2)
        # + * CLOSE is n % above AVG
        self.CoverCxN =     self.compare(price=self.CLOSE, type='gt', against=self.AVG_PRICE * self.CLOSE_X_N)


    def xunder(self,**kwargs):
        rs = False
        df = kwargs['df']
        dfl = kwargs['dfl']
        varval = kwargs['trigger']
        refval = kwargs['against']
        current_varval = df[varval].iloc[len(df.index)-1]
        prev_varval =df[varval].iloc[len(df.index)-2]

        if prev_varval > refval and current_varval < refval:
            rs = True
        return rs

    def xover(self,**kwargs):
        rs = False
        df = kwargs['df']
        dfl = kwargs['dfl']
        varval = kwargs['trigger']
        refval = kwargs['against']
        current_varval = df[varval].iloc[len(df.index)-1]
        prev_varval =df[varval].iloc[len(df.index)-2]

        if prev_varval < refval and current_varval >= refval:
            rs = True
        return rs


    def compare(self,**kwargs):
        ctype = kwargs['type']
        price = kwargs['price']
        against = kwargs['against']

        if ctype == 'lt':
            if price < against:
                # + print("TRUE")
                return True
            else:
                pass  # + print("FALSE")
            return False

        if ctype == 'gt':
            if price > against:
                # + print("TRUE")
                return True
            else:
                pass  # + print("FALSE")
            return False
        if ctype == 'lte':
            if price <= against:
                # + print("TRUE")
                return True
            else:
                pass  # + print("FALSE")
            return False

        if ctype == 'gte':
            if price >= against:
                # + print("TRUE")
                return True
            else:
                pass  # + print("FALSE")
            return False

    def buytest(self, test):
        g.buyfiltername = test
        call = f"self.{test}()"
        return eval(call)

    def selltest(self, test):
        g.sellfiltername = test
        call = f"self.{test}()"
        return eval(call)

    # + ! special case BUY tests
    def BUY_never(self):
        return False

    # + * special case SELL tests
    def BUY_always(self):
        FLAG=True
        # FLAG = FLAG and self.compare(price = self.CLOSE, type='lt', against = self.OPEN)
        return FLAG

    def SELL_never(self):
        return False

    def SELL_always(self):
        FLAG=True
        # FLAG = FLAG and self.compare(price = self.CLOSE, type='gt', against = self.OPEN)
        return FLAG



    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_tvb(self):
        FLAG = True
        # g.df_buysell['mclr'].iloc[0] = "red"

        # !FLAG = FLAG and self.FFMAPS_UPTURN and self.BBDELTA > o.cvars.get('bbDelta_lim') and self.CLOSE < self.MAVLONG and self.AMP > 6
        # !FLAG = FLAG or self.xunder(trigger="Close", against=self.LOWERCLOSE, dfl=self.dfl, df=self.df)

        FLAG = FLAG and self.FFMAPS < g.ffmaps_hithresh
        FLAG = FLAG and self.FFMAPS_UPTURN
        # FLAG = FLAG and self.BBDELTA > o.cvars.get('bbDelta_lim')
        FLAG = FLAG and self.CLOSE < self.MAVLONG
        FLAG = FLAG and self.AMP > g.amp_lim
        # FLAG = FLAG and g.sigffdeltahi > g.sigffdeltahi_lim


        # FLAG = FLAG and self.df['sigff'][-1] < self.df['sigff'][-2]


        # FLAG = FLAG and self.MAVLONG < self.MAVLONGER
        # FLAG = FLAG and self.MAVLONG < self.MAVLONGEST
        FLAG = FLAG and self.CLOSE < o.state_r('last_buy_price')
        g.buymode = "L"

        if o.cvars.get('xflag01'):
            COND2 = (
                    self.xunder(trigger="Close", against=self.LBLOW, dfl=self.dfl, df=self.df)
                    and self.CLOSE < o.state_r('last_buy_price')
                    # and g.sigffdeltahi < g.sigffdeltahi_lim
                    and self.AMP < g.amp_lim
            )

            if COND2:
                g.buymode = "D"
                g.df_buysell['mclr'].iloc[0] = 1

            FLAG = FLAG or COND2


        # FLAG = FLAG and self.xunder(trigger="Histogram", against=0, dfl=self.dfl, df=self.df)
        # FLAG = FLAG and self.xover(trigger="MACD", against=self.SIGNAL, dfl=self.dfl, df=self.df)
        # FLAG = FLAG and self.MACD< 0

        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_tvb(self):
        FLAG = True
        # FLAG = FLAG and self.Cover3BBhigh
        # FLAG = FLAG or (
        #         self.xover(trigger="bbl0", against=self.BB_LOW_2, dfl=self.dfl, df=self.df)
        #         and self.CLOSE > self.AVG_PRICE
        # )

        thisClose = self.df['Close'].iloc[len(self.df.index)-1]

        total_fee = g.running_buy_fee + g.est_sell_fee
        covercost = total_fee * (1 / g.subtot_qty)
        coverprice = covercost + g.avg_price

        # print(f"-----------------------------AVG:")
        # print(f"  {g.avg_price} COVERCOST: {est_buy_fee+est_sell_fee} = {est_buy_fee} + {est_sell_fee} FILL: {fullcost}")

        FLAG = FLAG and self.FFMAPS_DNTURN
        FLAG = FLAG and self.FFMAPS > 0
        # FLAG = FLAG and self.df['sigff'][-1] > self.df['sigff'][-2]
        FLAG = FLAG or thisClose > coverprice

        # if self.FFMAPS_DNTURN and self.FFMAPS > 0:
        #     FLAG = FLAG and True
        # else:
        #     FLAG = FLAG and thisClose > fullcost
        # FLAG = FLAG or self.CLOSE > fullcost


        #and self.CLOSE > (self.AVG_PRICE + g.covercost)
        # print(f"tesfor for voer: {g.covercost}")
        # FLAG = FLAG and self.CLOSE > (g.avg_price + (g.covercost*2))
        # FLAG = FLAG and (
        #
        #         self.CLOSE > self.BB_HIGH_1   #!red
        #         # self.CLOSE > self.BB_HIGH_2  #*green
        #         # and self.CLOSE < self.BB_LOW_3
        # )

        #
        # FLAG = FLAG and self.Cover3BBhigh
        # FLAG = FLAG or (
        #         # self.xover(trigger="bbl0", against=self.BB_LOW_2, dfl=self.dfl, df=self.df)
        #         # and self.xover(trigger='ffmap2', against=self.FFMAPLLIM2, dfl=self.dfl, df=self.df)
        #         self.CLOSE > self.AVG_PRICE * 1.002
        # )
        #

        return FLAG


    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_Clt3LowBands(self):
        FLAG = True
        FLAG = FLAG and self.Cunder3BBlow
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_Llt3LowBands(self):
        FLAG = True
        FLAG = FLAG and self.LOW < self.BB_LOW_0
        FLAG = FLAG and self.LOW < self.BB_LOW_1
        FLAG = FLAG and self.LOW < self.BB_LOW_2
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_CltLowBbavg(self):
        FLAG = True
        FLAG = FLAG and self.CLOSE < self.BB3_LOW_AVG
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_CltMidBbavg(self):
        FLAG = True
        FLAG = FLAG and self.CLOSE < self.BB3_MID_AVG
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_CltLowBbavg_ffmapLow(self):
        FLAG = True
        FLAG = FLAG and self.CLOSE < self.BB3_LOW_AVG
        FLAG = FLAG or self.xunder(trigger = self.df['ffmap'], against=self.FFMAPLLIM)

        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_ffmapXUlow(self):
        FLAG = True
        FLAG = FLAG and self.xunder(side="BUY",trigger = self.df['ffmap'], against=self.FFMAPLLIM)
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_ffmapXOlow(self):
        FLAG = True
        FLAG = FLAG and self.xover(side="BUY",trigger = self.df['ffmap'], against=self.FFMAPLLIM)
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_LltLowBbavg(self):
        FLAG = True
        FLAG = FLAG and self.LOW < self.BB3_LOW_AVG
        return FLAG
    # ! ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def BUY_CltPctlim(self):
        FLAG = True
        FLAG = FLAG and self.CLOSE < self.AVG_PRICE * 0.995
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_Cgt3HiBands_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.Cover3BBhigh  # + * HIGH is above all three BB high bands
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_Cgt3HiBands(self):
        FLAG = True
        FLAG = FLAG and self.Cover3BBhigh  # + * HIGH is above all three BB high bands
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_Hgt3HiBands_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.Hover3BBhigh
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_HgtHiBbavg(self):
        FLAG = True
        FLAG = FLAG and self.HIGH > self.BB3_UP_AVG
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_HgtHiBbavg_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.HIGH > self.BB3_UP_AVG
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_HgtHiBbavg_CoA_ffmapLow(self):
        FLAG = True
        FLAG = FLAG and self.CoA and (
            self.HIGH > self.BB3_UP_AVG
            or
            self.xunder(trigger=self.df['ffmap2'], against=self.FFMAPLLIM2)
        )
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_HgtHiBbavg_ffmapLow(self):
        FLAG = True
        FLAG = FLAG and (
            self.HIGH > self.BB3_UP_AVG
            or
            self.xunder(trigger=self.df['ffmap2'], against=self.FFMAPLLIM2)
        )
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_HgtHiBbavg_ffmapLowCoA(self):
        FLAG = True
        FLAG = FLAG and (
            self.HIGH > self.BB3_UP_AVG
            or
            (
                self.xunder(trigger=self.df['ffmap2'], against=self.FFMAPLLIM2)
                and 
                self.CLOSE > self.AVG_PRICE
            )
        )
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_CgtHiBbavg_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.CLOSE > self.BB3_UP_AVG
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_ffmapXUlow(self):
        FLAG = True
        FLAG = FLAG and self.xunder(trigger = self.df['ffmap2'], against=self.FFMAPLLIM2)
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_ffmapXUlowCoA(self):
        FLAG = True
        FLAG = FLAG and self.xunder(trigger = self.df['ffmap2'], against=self.FFMAPLLIM2)
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_ffmapXOlow(self):
        FLAG = True
        FLAG = FLAG and self.xunder(trigger = self.df['ffmap2'], against=self.FFMAPLLIM2)
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_ffmapXUlow_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.xunder(trigger = self.df['ffmap2'], against=self.FFMAPLLIM2)
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_ffmapXOlow_CoA(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.xunder(trigger = self.df['ffmap2'], against=self.FFMAPLLIM2)
        return FLAG
    # * ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
    def SELL_CgtPctlim(self):
        FLAG = True
        FLAG = FLAG and self.CoA
        FLAG = FLAG and self.CLOSE > self.AVG_PRICE * 1.005
        return FLAG


