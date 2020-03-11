# This code is for sample purposes only, comes as is and with no warranty or guarantee of performance
import json
from collections    import OrderedDict
from datetime       import datetime
from os.path        import getmtime
from time           import sleep
from datetime import date, timedelta
from utils          import ( get_logger, lag, print_dict, print_dict_of_dicts, sort_by_key,
                             ticksize_ceil, ticksize_floor, ticksize_round )
import quantstats as qs

import ccxt
import requests
import pandas as pd
from finta import TA

import json

import copy as cp
import argparse, logging, math, os, pathlib, sys, time, traceback

try:
    from deribit_api    import RestClient
except ImportError:
    #print("Please install the deribit_api pacakge", file=sys.stderr)
    #print("    pip3 install deribit_api", file=sys.stderr)
    exit(1)

# Add command line switches
parser  = argparse.ArgumentParser( description = 'Bot' )

# Use production platform/account
parser.add_argument( '-p',
                     dest   = 'use_prod',
                     action = 'store_true' )

# Do not display regular status updates to terminal
parser.add_argument( '--no-output',
                     dest   = 'output',
                     action = 'store_false' )

# Monitor account only, do not send trades
parser.add_argument( '-m',
                     dest   = 'monitor',
                     action = 'store_true' )

# Do not restart bot on errors
parser.add_argument( '--no-restart',
                     dest   = 'restart',
                     action = 'store_false' )
qs.extend_pandas()

# fetch the daily returns for a stock

from datetime import datetime 
#data = {}
#stock = qs.utils.download_returns('FB')
#data = {0: 0, 1: -1, 2: 1, 3: -1, 4: 2, 5:-3, 6: 10}
#{(datetime.strptime('2020-02-28', '%Y-%m-%d')): 0,(datetime.strptime(datetime.today().strftime('%Y-%m-%d'), '%Y-%m-%d')): -1}
#s = pd.Series(data)

##print(s)
##print(qs.stats.max_drawdown(s))

args    = parser.parse_args()
URL     = 'https://www.deribit.com'#ctrl+h!!!!!
skews = []

KEY     = ''
SECRET  = ''
BP                  = 1e-4      # one basis point
BTC_SYMBOL          = 'btc'
CONTRACT_SIZE       = 10       # USD
COV_RETURN_CAP      = 1000       # cap on variance for vol estimate
DECAY_POS_LIM       = 0.1       # position lim decay factor toward expiry
EWMA_WGT_COV        = 66         # parameter in % points for EWMA volatility estimate
EWMA_WGT_LOOPTIME   = 2.5      # parameter for EWMA looptime estimate
FORECAST_RETURN_CAP = 100        # cap on returns for vol estimate
LOG_LEVEL           = logging.INFO
MIN_ORDER_SIZE      = 10
MAX_LAYERS          =  3# max orders to layer the ob with on each side
MKT_IMPACT          =  0.5      # base 1-sided spread between bid/offer
NLAGS               =  2        # number of lags in time series
PCT                 = 100 * BP  # one percentage point
PCT_LIM_LONG        = 55      # % position limit long
PCT_LIM_SHORT       = 55 # % position limit short
PCT_QTY_BASE        = 85 # pct order qty in bps as pct of acct on each order
MIN_LOOP_TIME       =  0.25      # Minimum time between loops
RISK_CHARGE_VOL     =   85.5  # vol risk charge in bps per 100 vol
SECONDS_IN_DAY      = 3600 * 24
SECONDS_IN_YEAR     = 365 * SECONDS_IN_DAY
WAVELEN_MTIME_CHK   = 15        # time in seconds between check for file change
WAVELEN_OUT         = 15        # time in seconds between output to terminal
WAVELEN_TS          = 15        # time in seconds between output to terminal
WAVELEN_TS2         = 150        # time in seconds between time series update
VOL_PRIOR           = 150       # vol estimation starting level in percentage pts
INDEX_MOD = 0.02 #multiplier on modifer for bitmex XBTUSD / BXBT (index) diff as divisor for quantity, and as a multiplier on riskfac (which increases % difference among order prices in layers)
POS_MOD = 0.15#multiplier on modifier for position difference vs min_order_size as multiplier for quantity
PRICE_MOD = 0.02 # for price == 2, the modifier for the PPO strategy as multiplier for quantity

EWMA_WGT_COV        *= PCT
MKT_IMPACT          *= BP
PCT_LIM_LONG        *= PCT
PCT_LIM_SHORT       *= PCT
PCT_QTY_BASE        *= BP
VOL_PRIOR           *= PCT

TP = 0.15
SL = -0.062
avgavgpnls = []
class MarketMaker( object ):
    
    def __init__( self, monitor = True, output = True ):
        self.equity_usd         = None
        self.tps = 0
        self.sls = 0
        self.equity_btc         = None
        self.eth = 0
        self.equity_usd_init    = None
        self.equity_btc_init    = None
        self.con_size           = float( CONTRACT_SIZE )
        self.client             = None
        self.deltas             = OrderedDict()
        self.futures            = OrderedDict()
        self.futures_prv        = OrderedDict()
        self.logger             = None
        self.volatility = 0
        
        self.bbw = {}
        self.atr = {}
        self.diffdeltab = {}
        self.diff2 = 0
        self.diff3 = 0
        self.bands = {}
        self.quantity_switch = []
        self.price = []
        self.buysellsignal = {}
        self.directional = []
        self.seriesData = {}
        self.seriesData[(datetime.strptime((date.today() - timedelta(days=1)).strftime('%Y-%m-%d'), '%Y-%m-%d'))] = 0
            
        self.seriesPercent = {}
        self.startUsd = {}
        self.firstfirst = True
        self.dsrsi = 50
        self.minMaxDD = None
        self.arbmult = {}
        self.thearb = 0
        self.maxMaxDD = None
        self.ws = {}
        self.ohlcv = {}
        self.mean_looptime      = 1
        self.monitor            = monitor
        self.output             = output or monitor
        self.positions          = OrderedDict()
        self.spread_data        = None
        self.this_mtime         = None
        self.ts                 = None
        self.vols               = OrderedDict()
        self.multsShort = {}
        self.multsLong = {}
        self.wantstomarket = 0
        self.marketed = 0
        self.waittilmarket = 0
        self.lastposdiff = 1
        self.posdiff = 1
        self.diff = 1
        with open('deribit-settings.json', 'r') as read_file:
            data = json.load(read_file)

            self.maxMaxDD = data['maxMaxDD']
            self.minMaxDD = data['minMaxDD']
            self.directional = data['directional']
            self.price = data['price']
            self.volatility = data['volatility']
            self.quantity_switch = data['quantity']
    def create_client( self ):
        self.client = RestClient( KEY, SECRET, URL )

    def get_bbo( self, contract ): # Get best b/o excluding own orders
        j = self.ohlcv[contract].json()
        fut2 = contract
        #print(contract)
        best_bids = []
        best_asks = []
        o = []
        h = []
        l = []
        c = []
        v = []
        for b in j['result']['open']:
            o.append( b )
    
        for b in j['result']['high']:
            h.append(b)
        for b in j['result']['low']:
            l.append(b)
        for b in j['result']['close']:
            c.append(b)
        for b in j['result']['volume']:
            v.append(b)
        abc = 0
        ohlcv2 = []
        for b in j['result']['open']:
            ohlcv2.append([o[abc], h[abc], l[abc], c[abc], v[abc]])
            abc = abc + 1
    
        ddf = pd.DataFrame(ohlcv2, columns=['open', 'high', 'low', 'close', 'volume'])
        
        if 1 in self.directional:
            sleep(0)
            
            try:
                self.dsrsi = TA.STOCHRSI(ddf).iloc[-1] * 100
            except: 
                self.dsrsi = 50           
            ##print(self.dsrsi)
        # Get orderbook
        if 2 in self.volatility or 3 in self.price or 4 in self.quantity_switch:
            self.bands[fut2] = TA.BBANDS(ddf).iloc[-1]
            self.bbw[fut2] = (TA.BBWIDTH(ddf).iloc[-1])
            #print(float(self.bands[fut2]['BB_UPPER'] - self.bands[fut2]['BB_LOWER']))
            if (float(self.bands[fut2]['BB_UPPER'] - self.bands[fut2]['BB_LOWER'])) > 0:
                deltab = (self.get_spot() - self.bands[fut2]['BB_LOWER']) / (self.bands[fut2]['BB_UPPER'] - self.bands[fut2]['BB_LOWER'])
                if deltab > 50:
                    self.diffdeltab[fut2] = (deltab - 50) / 100 + 1
                if deltab < 50:
                    self.diffdeltab[fut2] = (50 - deltab) / 100 + 1
            else:
                self.diffdeltab[fut2] = 25 / 100 + 1
        if 3 in self.volatility:
            self.atr[fut2] = TA.ATR(ddf).iloc[-1]
            
        if 0 in self.price:
            ob      = self.client.getorderbook( contract )
            bids    = ob[ 'bids' ]
            asks    = ob[ 'asks' ]
            
            ords        = self.client.getopenorders( contract )
            bid_ords    = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
            ask_ords    = [ o for o in ords if o[ 'direction' ] == 'sell' ]
            best_bid    = None
            best_ask    = None

            err = 10 ** -( self.get_precision( contract ) + 1 )
            
            for b in bids:
                match_qty   = sum( [ 
                    o[ 'quantity' ] for o in bid_ords 
                    if math.fabs( b[ 'price' ] - o[ 'price' ] ) < err
                ] )
                if match_qty < b[ 'quantity' ]:
                    best_bid = b[ 'price' ]
                    break
            
            for a in asks:
                match_qty   = sum( [ 
                    o[ 'quantity' ] for o in ask_ords 
                    if math.fabs( a[ 'price' ] - o[ 'price' ] ) < err
                ] )
                if match_qty < a[ 'quantity' ]:
                    best_ask = a[ 'price' ]
                    break
            
            best_asks.append(best_ask)
            best_bids.append(best_bid)
        if 1 in self.price:
            dvwap = TA.VWAP(ddf)
            ##print(dvwap)
            tsz = self.get_ticksize( contract ) 
            try:   
                bid = ticksize_floor( dvwap.iloc[-1], tsz )
                ask = ticksize_ceil( dvwap.iloc[-1], tsz )
            except:
                bid = ticksize_floor( self.get_spot(), tsz )
                ask = ticksize_ceil( self.get_spot(), tsz )
           
            #print( { 'bid': bid, 'ask': ask })
            best_asks.append(best_ask)
            best_bids.append(best_bid)
        if 2 in self.quantity_switch:
            
            dppo = TA.PPO(ddf)
            self.buysellsignal[fut2] = 1
            try:
                if(dppo.iloc[-1].PPO > 0):
                    self.buysellsignal[fut2] = self.buysellsignal[fut2] * (1+PRICE_MOD)
                else:
                    self.buysellsignal[fut2] = self.buysellsignal[fut2] * (1-PRICE_MOD)

                if(dppo.iloc[-1].HISTO > 0):
                    self.buysellsignal[fut2] = self.buysellsignal[fut2]* (1+PRICE_MOD)
                else:
                    self.buysellsignal[fut2] = self.buysellsignal[fut2] * (1-PRICE_MOD)
                if(dppo.iloc[-1].SIGNAL > 0):
                    self.buysellsignal[fut2] = self.buysellsignal[fut2] * (1+PRICE_MOD)
                else:
                    self.buysellsignal[fut2] = self.buysellsignal[fut2] * (1-PRICE_MOD)
            except:
                self.buysellsignal[fut2] = 1

        
            ##print({ 'bid': best_bid, 'ask': best_ask })
        return { 'bid': self.cal_average(best_bids), 'ask': self.cal_average(best_asks) }


    def get_futures( self ): # Get all current futures instruments
        
        self.futures_prv    = cp.deepcopy( self.futures )
        insts               = self.client.getinstruments()
        self.futures        = sort_by_key( { 
            i[ 'instrumentName' ]: i for i in insts  if 'BTC-27MAR20' not in i['instrumentName'] and ('BTC-' in i['instrumentName'])  and i[ 'kind' ] == 'future'#  
        } )
        
        for k, v in self.futures.items():
            self.futures[ k ][ 'expi_dt' ] = datetime.strptime( 
                                                v[ 'expiration' ][ : -4 ], 
                                                '%Y-%m-%d %H:%M:%S' )
                        
        
    def get_pct_delta( self ):         
        self.update_status()
        return sum( self.deltas.values()) / self.equity_btc
    
    def get_eth( self ):
        r = requests.get('https://api.binance.com/api/v1/ticker/price?symbol=ETHUSDT').json()
        return float(r['price'])
    def get_spot( self ):
        return self.client.index()[ 'btc' ]
    
    def get_precision( self, contract ):
        return self.futures[ contract ][ 'pricePrecision' ]

    
    def get_ticksize( self, contract ):
        return self.futures[ contract ][ 'tickSize' ]
    
    
    def output_status( self ):
        startLen = (len(self.seriesData))
        if self.startUsd != {}:
            startUsd = self.startUsd
            nowUsd = self.equity_usd
            diff = 100 * ((nowUsd / startUsd) -1)
            #print('diff')
            #print(diff)
            
            if diff < self.diff2:
                self.diff2 = diff
            if diff > self.diff3:
                self.diff3 = diff
            if self.diff3 > self.maxMaxDD:
                print('broke max max dd! sleep 24hr')
                self.client.cancelall()
                self.sls = self.sls + 1
                try:
                    for p in self.client.positions():
                        sleep(0.15)
                        if 'ETH' in p['instrument']:
                            size = p['size']
                        else:
                            size = p['size']
                        direction = p['direction']
                        if direction == 'buy':
                            size = size
                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )

                        else:
                            if size < 0:
                                size = size * -1
                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
                    sleep(60 * 11)
                except Exception as e:
                    print(e)
                time.sleep(60 * 60 * 24)

                self.diff3 = 0
                self.startUsd = self.equity_usd
            if self.diff2 < self.minMaxDD:
                print('broke min max dd! sleep 24hr')
                self.client.cancelall()
                self.sls = self.sls + 1
                try:
                    for p in self.client.positions():
                        sleep(0.15)
                        if 'ETH' in p['instrument']:
                            size = p['size']
                        else:
                            size = p['size']
                        direction = p['direction']
                        if direction == 'buy':
                            size = size
                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )

                        else:
                            if size < 0:
                                size = size * -1
                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
                    sleep(60 * 11)
                except Exception as e:
                    print(e)
                time.sleep(60 * 60 * 24)
                self.diff2 = 0
                self.startUsd = self.equity_usd
            self.seriesData[(datetime.strptime(datetime.today().strftime('%Y-%m-%d'), '%Y-%m-%d'))] = self.diff2
            
            endLen = (len(self.seriesData))
            if endLen != startLen:
                self.seriesPercent[(datetime.strptime(datetime.today().strftime('%Y-%m-%d'), '%Y-%m-%d'))] = diff
                self.diff2 = 0
                self.diff3 = 0
                self.startUsd = self.equity_usd
            s = pd.Series(self.seriesData)


            #print(s)
            #print(qs.stats.max_drawdown(s))
        if not self.output:
            return None
        
        self.update_status()
        
        now     = datetime.utcnow()
        days    = ( now - self.start_time ).total_seconds() / SECONDS_IN_DAY
        print( '********************************************************************' )
        print( 'Start Time:        %s' % self.start_time.strftime( '%Y-%m-%d %H:%M:%S' ))
        print( 'Current Time:      %s' % now.strftime( '%Y-%m-%d %H:%M:%S' ))
        print( 'Days:              %s' % round( days, 1 ))
        print( 'Hours:             %s' % round( days * 24, 1 ))
        print( 'Spot Price:        %s' % self.get_spot())
        
        
        pnl_usd = self.equity_usd - self.equity_usd_init
        pnl_btc = self.equity_btc - self.equity_btc_init
        if self.firstfirst == True:
            self.startUsd = self.equity_usd
            self.firstfirst = False
        print( 'Equity ($):        %7.2f'   % self.equity_usd)
        print( 'P&L ($)            %7.2f'   % pnl_usd)
        print( 'Equity (BTC):      %7.4f'   % self.equity_btc)
        print( 'P&L (BTC)          %7.4f'   % pnl_btc)
        ##print( '%% Delta:           %s%%'% round( self.get_pct_delta() / PCT, 1 ))
        ##print( 'Total Delta (BTC): %s'   % round( sum( self.deltas.values()), 2 ))        
        #print_dict_of_dicts( {
        #    k: {
        #        'BTC': self.deltas[ k ]
        #    } for k in self.deltas.keys()
        #    }, 
        #    roundto = 2, title = 'Deltas' )
        
        print_dict_of_dicts( {
            k: {
                'Contracts': self.positions[ k ][ 'size' ]
            } for k in self.positions.keys()
            }, 
            title = 'Positions' )
        positionSize = 0
        positionPos = 0
        for p in self.positions:
            positionSize = positionSize + self.positions[p]['size']
            if self.positions[p]['size'] < 0:
                positionPos = positionPos - self.positions[p]['size']
            else:   
                positionPos = positionPos + self.positions[p]['size']
        print(' ')
        print('Position total delta: ' + str(positionSize * 10) + '$')
        if positionSize < 0:
            skews.append(-1)
        else:
            skews.append(1)
        theskew = 0
        count = 0
        for s in skews:
            theskew = theskew + s
            count = count + 1
        print('Skews: ' + str(theskew / count))
        print('Position exposure: ' + str(positionPos * 10) + '$')
        total = 0
        maximum = -99999999999999999999
        minimum = 999999999999999999999
        count = 0
        for pnl in avgavgpnls:
            if pnl > maximum:
                maximum = pnl
            if pnl < minimum:
                minimum = pnl
            total = total + pnl
            count = count + 1
        if count > 0:
            avg = total / count
            print('recent pnl: ' + str(avgavgpnls[-1]) + ' avg avg pnl: ' + str(avg) + ' min: ' + str(minimum) + ' max: ' + str(maximum))
            print('tps: ' + str(self.tps) + ' & sls: ' + str(self.sls))
        if not self.monitor:
            print_dict_of_dicts( {
                k: {
                    '%': self.vols[ k ]
                } for k in self.vols.keys()
                }, 
                multiple = 100, title = 'Vols' )
            #print( '\nMean Loop Time: %s' % round( self.mean_looptime, 2 ))
            #print( '' )
            for k in self.positions.keys():


                if 'sizeEth' in self.positions[k]:
                    key = 'sizeEth'
                    spot = self.get_eth()
                else:
                    key = 'sizeBtc'
                    spot = self.get_spot()
                #print(self.positions[k][key])
                if self.positions[k]['size'] > 100:
                    self.multsShort[k] = (self.positions[k]['size'] / 50) * POS_MOD
                if self.positions[k]['size'] < (-1 * 100):
                    self.multsLong[k] = (-1 * self.positions[k]['size'] / 50) * POS_MOD
#Vols           
            print(self.multsLong)
            print(self.multsShort)
        
    def place_orders( self ):

        if self.monitor:
            return None
        
        con_sz  = self.con_size        
        
        for fut in self.futures.keys():
            self.avg_pnl_sl_tp()
            account         = self.client.account()

            spot            = self.get_spot()
            bal_btc         = account[ 'equity' ] * 100
            pos_lim_long    = bal_btc * PCT_LIM_LONG / len(self.futures)
            pos_lim_short   = bal_btc * PCT_LIM_SHORT / len(self.futures)

            if 'PERPETUAL' in fut:
                pos_lim_short = pos_lim_short * (len(self.futures)  - 1)
                pos_lim_long = pos_lim_long * (len(self.futures)- 1)
            
            expi            = self.futures[ fut ][ 'expi_dt' ]
            ##print(self.futures[ fut ][ 'expi_dt' ])
            if self.eth is 0:
                self.eth = 200
            if 'ETH' in fut:
                if 'sizeEth' in self.positions[fut]:
                    pos             = self.positions[ fut ][ 'sizeEth' ] * self.eth / self.get_spot() 
                else:
                    pos = 0
            else:
                pos             = self.positions[ fut ][ 'sizeBtc' ]

            tte             = max( 0, ( expi - datetime.utcnow()).total_seconds() / SECONDS_IN_DAY )
            pos_decay       = 1.0 - math.exp( -DECAY_POS_LIM * tte )
            #pos_lim_long   *= pos_decay
            #pos_lim_short  *= pos_decay
            

            pos_lim_long   -= pos
            pos_lim_short  += pos

            pos_lim_long    = max( 0, pos_lim_long  )
            pos_lim_short   = max( 0, pos_lim_short )

            min_order_size_btc = MIN_ORDER_SIZE / spot * CONTRACT_SIZE
            
            #yqbtc  = max( PCT_QTY_BASE  * bal_btc, min_order_size_btc)
            qtybtc = PCT_QTY_BASE  * bal_btc
            nbids   = min( math.trunc( pos_lim_long  / qtybtc ), MAX_LAYERS )
            nasks   = min( math.trunc( pos_lim_short / qtybtc ), MAX_LAYERS )
            positionSize = 0
            for p in self.positions:
                positionSize = positionSize + int(self.positions[p]['size'])

            #if 'PERPETUAL' in fut and self.thearb > 1 and positionSize < 0:
             #   nbids  = (nbids + (positionSize * -1)) # 30 / 10 = 3
            #    nbids = min(MAX_LAYERS * 1.5, nbids)
            if 'PERPETUAL' not in fut and float(self.thearb) < 1 and positionSize > 0:
                nbids  = (nbids + (positionSize)) / len(self.futures) 
                nbids = min(MAX_LAYERS, nbids)
            if 'PERPETUAL' in fut and self.thearb < 1 and positionSize < 0: 
                nasks  = (nasks + (positionSize * -1)) 
                nasks = min(MAX_LAYERS * 1.5, nasks)
            if 'PERPETUAL' not in fut and float(self.thearb) > 1 and positionSize > 0: #4 / 10 = 0.4
                nasks  = (nasks + (positionSize)) / len(self.futures) 
                nasks = min(MAX_LAYERS, nasks)

            nasks = int (nasks)
            nbids = int (nbids)
            place_bids = nbids > 0
            place_asks = nasks > 0
            #buy bid sell ask
            if self.dsrsi > 80: #over
                place_bids = 0
            if self.dsrsi < 20: #under
                place_asks = 0
            if not place_bids and not place_asks:
                #print( 'No bid no offer for %s' % fut, min_order_size_btc )
                continue
                
            tsz = self.get_ticksize( fut )            
            # Perform pricing
            vol = max( self.vols[ BTC_SYMBOL ], self.vols[ fut ] )
            if 1 in self.volatility:
                eps         = BP * vol * RISK_CHARGE_VOL
            if 0 in self.volatility:
                eps = BP * 0.5 * RISK_CHARGE_VOL
            if 2 in self.price:
                eps = eps * self.diff
            if 3 in self.price:
                if self.diffdeltab[fut] > 0 or self.diffdeltab[fut] < 0:
                    eps = eps *self.diffdeltab[fut]
            if 2 in self.volatility:
                eps = eps * (1+self.bbw[fut])
            if 3 in self.volatility:
                eps = eps * (self.atr[fut]/100)
            riskfac     = math.exp( eps )
            bbo     = self.get_bbo( fut )
            bid_mkt = bbo[ 'bid' ]
            ask_mkt = bbo[ 'ask' ]
            mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )

            mid_mkt = 0.5 * ( bid_mkt + ask_mkt )
            
            ords        = self.client.getopenorders( fut )
            cancel_oids = []
            bid_ords    = ask_ords = []
            
            if place_bids:
                
                bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                len_bid_ords    = min( len( bid_ords ), nbids )
                bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                bids    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]

                bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                
            if place_asks:
                
                ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                len_ask_ords    = min( len( ask_ords ), nasks )
                ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                asks    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]

                asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
            for i in range( max( nbids, nasks )):
                sleep(0.1)
                # BIDS
                #print('nbids')
                #print(nbids)
                #print('nasks')
                if place_bids and i < nbids:

                    if i > 0:
                        prc = ticksize_floor( min( bids[ i ], bids[ i - 1 ] - tsz ), tsz )
                    else:
                        prc = bids[ 0 ]

                    qty = round( prc * qtybtc / (con_sz / 1) ) 

                    if 4 in self.quantity_switch:
                        if self.diffdeltab[fut] > 0 or self.diffdeltab[fut] < 0:
                            qty = round(qty / (self.diffdeltab[fut])) 
                    if 2 in self.quantity_switch:
                        qty = round ( qty * self.buysellsignal[fut])    
                    if 3 in self.quantity_switch:
                        qty = round (qty *self.multsLong[fut])   
                    if 1 in self.quantity_switch:
                        qty = round (qty / self.diff) 
                      
                    if qty < 0:
                        qty = qty * -1
                    if 'ETH' in fut:
                        qty = round( (prc * qtybtc / (con_sz / 1)) * self.get_eth()) 
                        print(qty)
                    positionSize = 0
                    for p in self.positions:
                        positionSize = positionSize + self.positions[p]['size']

                    if 'PERPETUAL' in fut and self.thearb > 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures) 

                    elif 'PERPETUAL' not in fut and self.thearb > 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERPETUAL' not in fut and self.thearb < 1 and positionSize > 0:
                        qty = qty * 1.2#len(self.futures)
                    if i < len_bid_ords:    

                        
                        try:
                            oid = bid_ords[ i ][ 'orderId' ]
                            self.client.edit( oid, qty, prc )
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except:
                            try:
                                if self.arbmult[fut]['arb'] >= 1 and self.positions[fut]['size'] + qty / 2 < 0:
                                    self.client.buy( fut, qty, prc, 'true' )
                                if self.arbmult[fut]['arb'] <= 1 and 'PERPETUAL' not in fut or self.arbmult[fut]['arb'] > 1 and 'PERPETUAL' in fut:
                                    self.client.buy(  fut, qty, prc, 'true' )

                                if self.positions[fut]['size'] - qty / 2 >= 0:
                                    self.client.buy( fut, qty, prc, 'true' )
                                #cancel_oids.append( oid )
                                #self.logger.warn( 'Edit failed for %s' % oid )
                            except (SystemExit, KeyboardInterrupt):
                                raise
                            except Exception as e:
                                print(e)
                                if 'BTC-PERPETUAL' in str(e):
                                    try:
                                        if self.thearb <= 1 and 'PERPETUAL' not in fut or self.thearb > 1 and 'PERPETUAL' in fut:
                                            self.client.buy(  fut, qty, prc, 'true' )

                                    except Exception as e:
                                        print(e)
                                        #cancel_oids.append( oid )
                                        self.logger.warn( 'Bid order failed: %s bid for %s'
                                                % ( prc, qty ))
                    else:
                        
                        try:
                            oid = bid_ords[ i ][ 'orderId' ]
                            self.client.edit( oid, qty, prc )
                        except Exception as e:
                            #print(bid_ords)
                            abc = 1
                        try:
                            
                            if self.arbmult[fut]['arb'] >= 1 and self.positions[fut]['size'] - qty /  2<= 0:
                                self.client.buy( fut, qty, prc, 'true' )


                            if self.arbmult[fut]['arb'] <= 1:
                                self.client.buy(  fut, qty, prc, 'true' )


                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            if 'BTC-PERPETUAL' in str(e):
                                try:

                                    if self.thearb <= 1 and 'PERPETUAL' not in fut or self.thearb > 1 and 'PERPETUAL' in fut:
                                        self.client.buy(  fut, qty, prc, 'true' )
                                except Exception as e:
                                    print(e)
                                    #cancel_oids.append( oid )
                                    self.logger.warn( 'Bid order failed: %s bid for %s'
                                                % ( prc, qty ))

                # OFFERS

                if place_asks and i < nasks:

                    if i > 0:
                        prc = ticksize_ceil( max( asks[ i ], asks[ i - 1 ] + tsz ), tsz )
                    else:
                        prc = asks[ 0 ]
                        
                    qty = round( prc * qtybtc / (con_sz / 1) )
                      
                    #print(qty)
                    #print(qty)
                    #print(qty)
                    #print(qty)
                    if 4 in self.quantity_switch:
                        if self.diffdeltab[fut] > 0 or self.diffdeltab[fut] < 0:
                            qty = round(qty / (self.diffdeltab[fut])) 
                    
                    if 2 in self.quantity_switch:
                        qty = round ( qty / self.buysellsignal[fut])    
                    if 3 in self.quantity_switch:
                        qty = round (qty * self.multsShort[fut]) 
                        #print(qty)
                        #print(qty)
                        #print(qty)
                        #print(qty)
                    if 1 in self.quantity_switch:
                        qty = round (qty / self.diff)

                    if qty < 0:
                        qty = qty * -1    
                    if 'ETH' in fut:
                        
                        qty = round( (prc * qtybtc / (con_sz / 1)) * self.get_eth())
                    positionSize = 0
                    for p in self.positions:
                        positionSize = positionSize + self.positions[p]['size']
                    if 'PERPETUAL' in fut and self.thearb < 1 and positionSize < 0: 
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERPETUAL' not in fut and self.thearb < 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERPETUAL' not in fut and self.thearb > 1 and positionSize > 0:
                        qty = qty * 1.2#len(self.futures)
                    
                    if i < len_ask_ords:
                        
                        try:
                            oid = ask_ords[ i ][ 'orderId' ]
                            self.client.edit( oid, qty, prc )
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except:
                            try:
                                if place_asks and i < nasks:
                                    if self.arbmult[fut]['arb'] >= 1 and self.positions[fut]['size'] + qty / 2< 0:
                                        self.client.sell( fut, qty, prc, 'true' )
                                if self.arbmult[fut]['arb'] <= 1 and 'PERPETUAL' not in fut or self.arbmult[fut]['arb'] > 1 and 'PERPETUAL' in fut:
                                    self.client.sell(  fut, qty, prc, 'true' )

                                if place_bids and i < nbids:
                                    if self.positions[fut]['size'] + qty / 2< 0:
                                        self.client.buy( fut, qty, prc, 'true' )
                                #cancel_oids.append( oid )
                                #self.logger.warn( 'Sell Edit failed for %s' % oid )
                            except (SystemExit, KeyboardInterrupt):
                                raise
                            except Exception as e:
                                if 'BTC-PERPETUAL' in str(e):
                                    try:
                                        if place_bids and i < nbids:
                                            if self.thearb < 1 and 'PERPETUAL' in fut or 'PERPETUAL' in fut and self.positions[fut]['size'] + qty / 2< 0:
                                                self.client.buy( fut, qty, prc, 'true' )
                                        if place_asks and i < nasks:
                                            if self.positions[fut]['size'] - qty / 2 >= 0:
                                                self.client.sell( fut, qty, prc, 'true' )
                                    except Exception as e:
                                        print(e)
                                       # cancel_oids.append( oid )
                                
                                       # self.logger.warn( 'Sell Edit failed for %s' % oid )
                                        self.logger.warn( 'Offer order failed: %s at %s'
                                                        % ( qty, prc ))
                                #cancel_oids.append( oid )


                    else:
                        
                        try:
                            oid = ask_ords[ i ][ 'orderId' ]
                            self.client.edit( oid, qty, prc )
                        except:
                            #print('edit error')
                            abc = 1
                        try:
                            if self.arbmult[fut]['arb'] >= 1:
                                self.client.sell( fut, qty, prc, 'true' )


                            if self.arbmult[fut]['arb'] <= 1 and self.positions[fut]['size'] + qty / 2 >= 0:
                                self.client.sell(  fut, qty, prc, 'true' )

                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            if 'BTC-PERPETUAL' in str(e):
                                try:

                                    if place_bids and i < nbids:
                                        if self.thearb < 1 and 'PERPETUAL' in fut or 'PERPETUAL' in fut and self.positions[fut]['size'] + qty / 2< 0:
                                            self.client.buy( fut, qty, prc, 'true' )
                                    if place_asks and i < nasks:
                                        if  self.positions[fut]['size'] - qty / 2>= 0:
                                            self.client.sell( fut, qty, prc, 'true' )

                                except Exception as e:
                                    print(e)
                                    #cancel_oids.append( oid )
                                    self.logger.warn( 'Offer order failed: %s at %s'
                                                % ( qty, prc ))


            #if nbids < len( bid_ords ):
            #    cancel_oids += [ o[ 'orderId' ] for o in bid_ords[ nbids : ]]
            #if nasks < len( ask_ords ):
                #cancel_oids += [ o[ 'orderId' ] for o in ask_ords[ nasks : ]]

            for oid in cancel_oids:
                #print(oid)
                try:
                    self.client.cancel( oid )
                except:
                    self.logger.warn( 'Order cancellations failed: %s' % oid )
                                        
    
    def restart( self ):        
        try:
            strMsg = 'RESTARTING'
            #print( strMsg )
            self.client.cancelall()
            strMsg += ' '
            for i in range( 0, 5 ):
                strMsg += '.'
                print( strMsg )
                sleep( 1 )
        except:
            pass
        finally:
            os.execv( sys.executable, [ sys.executable ] + sys.argv )        
            

    def run( self ):
        
        self.run_first()
        self.output_status()

        t_ts = t_out = t_loop = t_mtime = datetime.utcnow()
        t_ts2 = t_out = t_loop = t_mtime = datetime.utcnow()

        while True:
            self.avg_pnl_sl_tp()
            self.get_futures()
            ethlist = []
            btclist = []
            for k in self.futures.keys():
                if 'ETH' in k:
                    ethlist.append(k)
                elif 'BTC' in k:
                    btclist.append(k)
            for k in ethlist:
                if 'PERPETUAL' not in k:
                    m = self.get_bbo(k)
                    bid = m['bid']
                    ask=m['ask']
                    
                    arb = bid/self.get_eth()
                    if arb > 1:
                        self.arbmult[k]=({"arb": arb, "long": k[:3]+"-PERPETUAL", "short": k})
                    if arb < 1:
                        self.arbmult[k]=({"arb": arb, "long":k, "short": k[:3]+"-PERPETUAL"})
                    self.thearb = arb
            for k in btclist:
                if 'PERPETUAL' not in k:
                    m = self.get_bbo(k)
                    bid = m['bid']
                    ask=m['ask']
                    
                    arb = bid/self.get_spot()
                    if arb > 1:
                        self.arbmult[k]=({"arb": arb, "long": k[:3]+"-PERPETUAL", "short": k})
                    if arb < 1:
                        self.arbmult[k]=({"arb": arb, "long":k, "short": k[:3]+"-PERPETUAL"})
                    self.thearb = arb
            #print(self.arbmult)       
            # Directional
            # 0: none
            # 1: StochRSI
            #
            # Price
            # 0: none
            # 1: vwap
            # 2: ppo
            #

            # Volatility
            # 0: none
            # 1: ewma
            self.avg_pnl_sl_tp()
            with open('deribit-settings.json', 'r') as read_file:
                data = json.load(read_file)

                self.maxMaxDD = data['maxMaxDD']
                self.minMaxDD = data['minMaxDD']
                self.directional = data['directional']
                self.price = data['price']
                self.volatility = data['volatility']
                self.quantity_switch = data['quantity']

            # Restart if a new contract is listed
            #if len( self.futures ) != len( self.futures_prv ):
                #self.restart()
            
            self.update_positions()
            self.avg_pnl_sl_tp()
            t_now   = datetime.utcnow()
            
            # Update time series and vols
            if ( t_now - t_ts ).total_seconds() >= WAVELEN_TS:
                t_ts = t_now
                for contract in self.futures.keys():
                    self.ohlcv[contract] = requests.get('https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name=' + contract + '&start_timestamp=' + str(int(time.time()) * 1000 - 1000 * 60 * 60) + '&end_timestamp=' + str(int(time.time())* 1000) + '&resolution=1')
            
                self.update_timeseries()
                self.update_vols()
            if ( t_now - t_ts2 ).total_seconds() >= WAVELEN_TS2:
                t_ts2 = t_now
                #self.client.cancelall()

            self.avg_pnl_sl_tp()
            positionSize = 0
            positionPos = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] < 0:
                    positionPos = positionPos - self.positions[p]['size']
                else:   
                    positionPos = positionPos + self.positions[p]['size']
            self.lastposdiff = self.posdiff #300
            self.posdiff = positionPos #400
            ts = 0
            ms = 0
            for fut in self.futures.keys():
                trades = self.client.tradehistory(1000, fut)
                for t in trades:
                    if t['liquidity'] == 'T':
                        ts = ts + t['amount']
                    else:
                        ms = ms + t['amount']
            diffratio = 1
            if ts > 0 and ms > 0:
                ratio = ts / ms
                diffratio = ratio / 0.2
                print('ratio: ' + str(ratio) + ' & diffratio: ' + str(diffratio))
            try:
                if positionSize > 0:
                    if self.marketed > 0:
                        self.marketed = 0
                    self.wantstomarket = positionSize / 10
                    self.waittilmarket = self.waittilmarket - 1
                    print('positionSize: ' + str(positionSize))
                    if positionSize > 35:
                        if self.waittilmarket <= 0 or self.posdiff / self.lastposdiff > 1.25:
                            size = self.wantstomarket + self.marketed
                            size = size / diffratio
                            print('size: ' + str(size))
                            if size > 0:

                                #self.marketed = self.marketed - size / 10
                                
                                self.wantstomarket = 0
                                self.waittilmarket = 0
                                #self.client.cancelall()
                                sleep(5)
                                print('waittilmarket 0 or pos/lastpos > 1.33, selling: ' + str(size) + ' and marketed: ' + str(self.marketed) + ' and pos/lastpos: ' + str(self.posdiff / self.lastposdiff))
                                counter = 0
                                for p in self.client.positions():

                                    sleep(0.15)
                                    direction = p['direction']
                                    if direction == 'buy':
                                        counter = counter + 1
                                if counter == 0:
                                    counter = counter + 1
                                sold = False
                                if counter > 0:
                                    size = size / counter
                                    for p in self.client.positions():
                                        ords        = self.client.getopenorders( p['instrument'] )
                                        #cancel_oids += [ o[ 'orderId' ] for o in ask_ords[ nasks : ]]
                                        for o in ords:
                                            if o['direction'] == 'sell':
                                                try:
                                                    sleep(0.1)
                                                    self.client.cancel( o['orderId'] )
                                                except:
                                                    abc = 1
                                        sleep(0.15)

                                        direction = p['direction']
                                        if direction == 'buy':
                                            sold = True
                                            size = size
                                            if 'ETH' in p['instrument']:
                                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                                            else:
                                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )
                                if sold == False:
                                    size = size / counter
                                    for p in self.client.positions():
                                        sleep(0.15)

                                        direction = p['direction']
                                        if direction == 'sell':
                                            size = size
                                            if 'ETH' in p['instrument']:
                                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                                            else:
                                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )

                else:
                    if self.marketed < 0:
                        self.marketed = 0
                    self.wantstomarket = positionSize / 10 * -1
                    self.waittilmarket = self.waittilmarket - 1
                    #-300
                    #-400\
                    if positionSize < -35:
                        if self.waittilmarket <= 0 or self.posdiff / self.lastposdiff < 0.80:
                            size = self.wantstomarket - self.marketed #12.25 - 16.5
                            size = size / diffratio
                            print('size: ' + str(size))
                            if size > 0:
                                self.wantstomarket = 0
                                self.waittilmarket = 0
                                #self.marketed = self.marketed + size / 10
                            
                                #self.client.cancelall()
                                sleep(5)
                                print('waittilmarket 0 or pos / lastpos < 0.75, buying: ' + str(size)  +' and marketed: ' + str(self.marketed) + ' and pos/lastpos: ' + str(self.posdiff / self.lastposdiff))
                                counter = 0
                                for p in self.client.positions():
                                    sleep(0.15)
                                    direction = p['direction']
                                    if direction == 'sell':
                                        counter = counter + 1
                                if counter == 0:
                                    counter = counter + 1
                                bought = False
                                if counter > 0:
                                    size = size / counter
                                    for p in self.client.positions():
                                        ords        = self.client.getopenorders( p['instrument'] )
                                        #cancel_oids += [ o[ 'orderId' ] for o in ask_ords[ nasks : ]]
                                        for o in ords:
                                            if o['direction'] == 'buy':
                                                try:
                                                    sleep(0.1)
                                                    self.client.cancel( o['orderId'] )
                                                except:
                                                    abc = 1
                                        sleep(0.15)

                                        direction = p['direction']
                                        if direction == 'sell':

                                            bought = True
                                            
                                            if 'ETH' in p['instrument']:
                                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                                            else:
                                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
                                if bought == False:
                                    size = size / counter
                                    for p in self.client.positions():
                                        sleep(0.15)

                                        direction = p['direction']
                                        if direction == 'buy':

                                            bought = True
                                            
                                            if 'ETH' in p['instrument']:
                                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                                            else:
                                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
            except Exception as e:
                print(e)
            self.place_orders()
            self.avg_pnl_sl_tp()
            # Display status to terminal
            if self.output:    
                t_now   = datetime.utcnow()
                if ( t_now - t_out ).total_seconds() >= WAVELEN_OUT:
                    self.output_status(); t_out = t_now
            
            # Restart if file change detected
            t_now   = datetime.utcnow()
            if ( t_now - t_mtime ).total_seconds() > WAVELEN_MTIME_CHK:
                t_mtime = t_now
                #if getmtime( __file__ ) > self.this_mtime:
                 #   self.restart()
            
            t_now       = datetime.utcnow()
            looptime    = ( t_now - t_loop ).total_seconds()
            self.avg_pnl_sl_tp()
            # Estimate mean looptime
            w1  = EWMA_WGT_LOOPTIME
            w2  = 1.0 - w1
            t1  = looptime
            t2  = self.mean_looptime
            
            self.mean_looptime = w1 * t1 + w2 * t2
            
            t_loop      = t_now
            positionSize = 0
            positionPos = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] < 0:
                    positionPos = positionPos - self.positions[p]['size']
                else:   
                    positionPos = positionPos + self.positions[p]['size']
            sleep_time  = MIN_LOOP_TIME - looptime 
            if sleep_time > 0 and (positionSize < -350 or positionSize > 350):
                time.sleep( sleep_time )
            if self.monitor:
                time.sleep( WAVELEN_OUT )
            self.avg_pnl_sl_tp()
    def cal_average(self, num):
        sum_num = 0
        for t in num:
            sum_num = sum_num + t           

        avg = sum_num / len(num)
        return avg

 
    def run_first( self ):
        
        self.create_client()
        self.client.cancelall()
        self.logger = get_logger( 'root', LOG_LEVEL )
        # Get all futures contracts
        self.get_futures()
        for k in self.futures.keys():
            self.ohlcv[k] = requests.get('https://www.deribit.com/api/v2/public/get_tradingview_chart_data?instrument_name=' + k + '&start_timestamp=' + str(int(time.time()) * 1000 - 1000 * 60 * 60) + '&end_timestamp=' + str(int(time.time())* 1000) + '&resolution=1')
            
            self.bbw[k] = 0
            self.bands[k] = []
            self.atr[k] = 0
            self.diffdeltab[k] = 0
            self.buysellsignal[k] = 1
       
        self.this_mtime = getmtime( __file__ )
        self.symbols    = [ BTC_SYMBOL ] + list( self.futures.keys()); self.symbols.sort()
        self.deltas     = OrderedDict( { s: None for s in self.symbols } )
        
        # Create historical time series data for estimating vol
        ts_keys = self.symbols + [ 'timestamp' ]; ts_keys.sort()
        
        self.ts = [
            OrderedDict( { f: None for f in ts_keys } ) for i in range( NLAGS + 1 )
        ]
        
        self.vols   = OrderedDict( { s: VOL_PRIOR for s in self.symbols } )
        
        self.start_time         = datetime.utcnow()
        self.update_status()
        self.equity_usd_init    = self.equity_usd
        self.equity_btc_init    = self.equity_btc
    def avg_pnl_sl_tp ( self ):
        pls = []
        account = self.client.account()
        for p in self.client.positions():
            try:
                if 'ETH' in p['instrument']:
                    pl = p['floatingPl']  / p['sizeEth'] * 100 # needs fixing
                else:
                    pl = p['floatingPl']  / account[ 'equity' ] 
                direction = p['direction']
               

                pls.append(pl)
            except:
                abc = 1
        total = 0
        count = 0
        for pl in pls:
            total = total + pl
            count = count + 1
        if count > 0:
            avg = total
            avgavgpnls.append(avg)
            #print('avg pl: ' + str(avg))
            if avg > TP:
                print('TP!')
                self.client.cancelall()
                self.tps = self.tps + 1
                positionSize = 0
                positionPos = 0
                for p in self.positions:
                    positionSize = positionSize + self.positions[p]['size']
                    if self.positions[p]['size'] < 0:
                        positionPos = positionPos - self.positions[p]['size']
                    else:   
                        positionPos = positionPos + self.positions[p]['size']
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('size: ' + str(size))
                try:
                    for p in self.client.positions():
                        sleep(0.15)

                        if selling:
                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )

                        else:
                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
                   #sleep(60 * 11)
                except:
                    abc = 1

            if avg < SL:
                print('SL!')
                self.update_positions()
                self.client.cancelall()
                self.sls = self.sls + 1
                positionSize = 0
                positionPos = 0
                for p in self.positions:
                    positionSize = positionSize + self.positions[p]['size']
                    print('positionSize: ' + str(positionSize))
                    if self.positions[p]['size'] < 0:
                        positionPos = positionPos - self.positions[p]['size']
                    else:   
                        positionPos = positionPos + self.positions[p]['size']
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('positionSize: ' + str(positionSize))
                size = size / len(self.client.positions())
                print('size: ' + str(size))
                try:
                    for p in self.client.positions():
                        sleep(0.15)
                        if selling:

                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, self.get_eth() * 0.9, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, self.get_spot() * 0.9, 'false' )

                        else:

                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, self.get_eth() * 1.1, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, self.get_spot() * 1.1, 'false' )
                    sleep(60 * 0.5)
                except Exception as e:
                    print(e)
    def update_status( self ):
        
        positionSize = 0
        positionPos = 0
        for p in self.positions:
            positionSize = positionSize + self.positions[p]['size']
            if self.positions[p]['size'] < 0:
                positionPos = positionPos - self.positions[p]['size']
            else:   
                positionPos = positionPos + self.positions[p]['size']
        account = self.client.account()
        spot    = self.get_spot()

        self.equity_btc = account[ 'equity' ]
        self.equity_usd = self.equity_btc * spot
        print('equity')
        print(self.equity_btc)
        self.update_positions()
        for k in self.positions.keys():

            self.multsShort[k] = 1
            self.multsLong[k] = 1
      #  self.deltas = OrderedDict( 
      #      { k: self.positions[ k ][ 'sizeBtc' ] for k in self.futures.keys()}
      #  )
      
      #  self.deltas[ BTC_SYMBOL ] = account[ 'equity' ]        
        
        
    def update_positions( self ):

        self.positions  = OrderedDict( { f: {
            'size':         0,
            'sizeBtc':      0,
            'indexPrice':   None,
            'markPrice':    None
        } for f in self.futures.keys() } )
        positions       = self.client.positions()
        
        for pos in positions:
            if 'ETH' in pos['instrument']:
                pos['size'] = pos['size'] / 10
            if pos[ 'instrument' ] in self.futures:
                self.positions[ pos[ 'instrument' ]] = pos
        
    
    def update_timeseries( self ):
        
        if self.monitor:
            return None
        
        for t in range( NLAGS, 0, -1 ):
            self.ts[ t ]    = cp.deepcopy( self.ts[ t - 1 ] )
        
        spot                    = self.get_spot()
        self.ts[ 0 ][ BTC_SYMBOL ]    = spot
        
        for contract in self.futures.keys():
            ob      = self.client.getorderbook( contract )
            bids    = ob[ 'bids' ]
            asks    = ob[ 'asks' ]
            
            ords        = self.client.getopenorders( contract )
            bid_ords    = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
            ask_ords    = [ o for o in ords if o[ 'direction' ] == 'sell' ]
            best_bid    = None
            best_ask    = None

            err = 10 ** -( self.get_precision( contract ) + 1 )
            
            for b in bids:
                match_qty   = sum( [ 
                    o[ 'quantity' ] for o in bid_ords 
                    if math.fabs( b[ 'price' ] - o[ 'price' ] ) < err
                ] )
                if match_qty < b[ 'quantity' ]:
                    best_bid = b[ 'price' ]
                    break
            
            for a in asks:
                match_qty   = sum( [ 
                    o[ 'quantity' ] for o in ask_ords 
                    if math.fabs( a[ 'price' ] - o[ 'price' ] ) < err
                ] )
                if match_qty < a[ 'quantity' ]:
                    best_ask = a[ 'price' ]
                    break
            bid = best_bid
            ask = best_ask

            if not bid is None and not ask is None:
                mid = 0.5 * ( bid + ask )
                
            else:
                continue
            self.ts[ 0 ][ contract ]               = mid
                
        self.ts[ 0 ][ 'timestamp' ]  = datetime.utcnow()

        
    def update_vols( self ):
        
        if self.monitor:
            return None
        
        w   = EWMA_WGT_COV
        ts  = self.ts
        
        t   = [ ts[ i ][ 'timestamp' ] for i in range( NLAGS + 1 ) ]
        p   = { c: None for c in self.vols.keys() }
        for c in ts[ 0 ].keys():
            p[ c ] = [ ts[ i ][ c ] for i in range( NLAGS + 1 ) ]
            
        if any( x is None for x in t ):
            return None
        for c in self.vols.keys():
            if any( x is None for x in p[ c ] ):
                return None
        
        NSECS   = SECONDS_IN_YEAR
        cov_cap = COV_RETURN_CAP / NSECS
        
        for s in self.vols.keys():
            
            x   = p[ s ]            
            #print(x)
            dx  = x[ 0 ] / x[ 1 ] - 1
            #print(dx)
            dt  = ( t[ 0 ] - t[ 1 ] ).total_seconds()
            v   = min( dx ** 2 / dt, cov_cap ) * NSECS
            v   = w * v + ( 1 - w ) * self.vols[ s ] ** 2
            self.vols[ s ] = math.sqrt( v )
                            

if __name__ == '__main__':
    
    try:
        mmbot = MarketMaker( monitor = args.monitor, output = args.output )
        mmbot.run()
    except( KeyboardInterrupt, SystemExit ):
        #print( "Cancelling open orders" )
        mmbot.client.cancelall()
        sys.exit()
    except Exception as e:
        print(e)
        #print( traceback.format_exc())
        if args.restart:
            mmbot.restart()
        