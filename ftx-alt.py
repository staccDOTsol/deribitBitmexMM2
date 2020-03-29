
pair = 'ALT-PERP'
binApi = "a8-WWjFmbWWSqY-dh0adi5mdIS36pkyoAd5nUM2E"
binSecret = "1PynpPuHFic2_B8vsM-31g6Dfcoxa6L-3GLAbYEp"



import random, string

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
import _thread
import os
import ccxt
from flask import Flask
from flask import flash, render_template, request, redirect

app = Flask(__name__)
app.secret_key = "coindexpoc_]K#)=fq;wAu-4zSu%xu}yer+/rw%(n"


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


ULTRACONSERVATIVE = True
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
MKT_IMPACT          =  0      # base 1-sided spread between bid/offer
NLAGS               =  2        # number of lags in time series
PCT                 = 100 * BP  # one percentage point
PCT_LIM_LONG        = 20      # % position limit long
PCT_LIM_SHORT       = 20 # % position limit short
PCT_QTY_BASE        = 100 # pct order qty in bps as pct of acct on each order
MIN_LOOP_TIME       =  0.25      # Minimum time between loops
RISK_CHARGE_VOL     =   250*16*2  # vol risk charge in bps per 100 vol
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



MAX_SKEW = 550
TP = 100.55
SL = -100.55
avgavgpnls = []
class MarketMaker( object ):
    
    def __init__( self, monitor = True, output = True ):
        self.predict_1 = 0.5
        self.predict_5 = 0.5
        self.slsinarow = 0
        self.equity_usd         = None
        self.equity_usd_2 = 0
        self.startUsd2 = 0
        self.tps = 0
        self.maxqty = 0
        self.sls = 0
        self.equity_btc         = None
        self.equity_usd2         = 0
        self.equity_btc2         = 0
        self.eth = 0
        self.equity_usd_init    = None
        self.equity_btc_init    = None
        self.con_size           = float( CONTRACT_SIZE )
        self.client             = None
        self.positionGains = {}
        self.arbplus = 0
        self.marketthreading = False
        self.imbuying = {}
        self.imselling = {}
        self.client2             = None
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
        self.positions2          = OrderedDict()
        self.spread_data        = None
        self.this_mtime         = None
        self.ts                 = None
        self.vols               = OrderedDict()
        self.multsShort = {}
        self.multsLong = {}
        self.ccxt = None
        self.wantstomarket = 0
        self.marketed = 0
        self.waittilmarket = 2
        self.cancelorder = 2
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
        binance_futures = ccxt.ftx(

            {
            "enableRateLimit": True,
            "apiKey": binApi,
            "secret": binSecret,
            "options":{"defaultMarket":"futures"}})
        
        self.client = binance_futures

        try:
            self.client2 = RestClient( KEY2, SECRET2, URL )
        except:
            print('only one key, all good')
    def get_bbo( self, contract ): # Get best b/o excluding own orders
        j = self.ohlcv[contract]
        fut2 = contract
        #print(contract)
        best_bids = []
        best_asks = []
        o = []
        h = []
        l = []
        c = []
        v = []
        for b in j:
            o.append(b[1])
            h.append(b[2])
            l.append(b[3])
            c.append(b[4])
            v.append(b[5])
        abc = 0
        ohlcv2 = []
        for b in j:
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
            ob = self.client.fetchOrderBook( contract )
            bids    = ob[ 'bids' ]
            asks    = ob[ 'asks' ]
            
            ords        = self.client.fetchOpenOrders( contract )
            #print(ords)
            bid_ords    = [ o for o in ords if o ['info'] [ 'side' ] == 'buy'  ]
            ask_ords    = [ o for o in ords if o ['info'] [ 'side' ] == 'sell' ]
            best_bid    = None
            best_ask    = None
            err = 10 ** -( self.get_precision( contract ) + 1 )
            
            for b in bids:
                match_qty   = sum( [ 
                    o['info']['size'] for o in bid_ords 
                    if math.fabs( b[0] - o['price'] ) < err
                ] )
                if match_qty < b[1]:
                    best_bid = b[0]
                    break
            
            for a in asks:
                match_qty   = sum( [ 
                    o['info']['size'] for o in ask_ords 
                    if math.fabs( a[0] - o['price'] ) < err
                ] )
                if match_qty < a[1]:
                    best_ask = a[0]
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

    def cancelall(self):
        for k in self.futures.keys():
            ords        = self.client.fetchOpenOrders( k )
            for order in ords:
                #print(order)
                oid = order ['info'] ['id']
               # print(order)
                try:
                    self.client.cancelOrder( oid , k )
                except Exception as e:
                    print(e)
    def get_futures( self ): # Get all current futures instruments
        
        self.futures_prv    = cp.deepcopy( self.futures )
        insts               = self.client.fetchMarkets()
        #print(insts[0])
        
        self.futures        = sort_by_key( { 
            i[ 'symbol' ]: i for i in insts   if 'MOVE' not in i['symbol'] and pair.split('-')[0] in i['symbol'] and i['type'] == 'future'
        } )
        print(self.futures)
        #for k, v in self.futures.items():
            #self.futures[ k ][ 'expi_dt' ] = datetime.strptime( 
            #                                   v[ 'expiration' ][ : -4 ], 
            #                                   '%Y-%m-%d %H:%M:%S' )
                        
        
    def get_pct_delta( self ):         
        self.update_status()
        return sum( self.deltas.values()) / self.equity_btc
    
    def get_eth( self ):
        r = requests.get('https://api.binance.com/api/v1/ticker/price?symbol=ETHUSDT').json()
        return float(r['price'])

    def get_btc( self ):
        return float(self.client.fetchTicker( 'BTC-PERP' )['bid'])

    def get_spot( self ):
        return float(self.client.fetchTicker( pair )['bid'])
    
    def get_precision( self, contract ):
        return self.futures[ contract ]['precision'][ 'amount' ]

    
    def get_ticksize( self, contract ):
        return float(self.futures[ contract ]['precision']['price' ])
    
    
    def output_status( self ):
        startLen = (len(self.seriesData))
        if self.startUsd != {}:
            startUsd = self.startUsd + self.startUsd2 
            nowUsd = self.equity_usd + self.equity_usd2
           
            


            diff = 100 * ((nowUsd / startUsd) -1)
            #print('diff')
            #print(diff)
            
            if diff < self.diff2:
                self.diff2 = diff
            if diff > self.diff3:
                self.diff3 = diff
            print('self diff3 : ' +str(self.diff3))
            if self.diff3 > self.maxMaxDD:
                print('broke max max dd! sleep 24hr')
                self.cancelall()
                self.sls = self.sls + 1
                try:
                    for p in self.client.privateGetPositions()['result']:
                        sleep(0.01)
                        size = float(p['size'])
                        if p['side'] == 'sell':
                            size = size * -1

                        if size < 0:
                            direction = 'sell'
                        else:
                            direction = 'buy'
                        if direction == 'buy':
                            size = size
                            bbo     = self.get_bbo( p['future'] )
                            bid_mkt = bbo[ 'bid' ]
                            ask_mkt = bbo[ 'ask' ]
                            mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                        else:

                            bbo     = self.get_bbo( p['future'] )
                            bid_mkt = bbo[ 'bid' ]
                            ask_mkt = bbo[ 'ask' ]
                            mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                            if size < 0:
                                size = size * -1
                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                    sleep(60 * 11)
                except Exception as e:
                    print(e)
                time.sleep(60 * 60 * 24)

                self.diff3 = 0
                self.startUsd2 = self.equity_usd2
                self.startUsd = self.equity_usd
            if self.diff2 < self.minMaxDD:
                print('broke min max dd! sleep 24hr')
                self.cancelall()
                self.sls = self.sls + 1
                try:
                    for p in self.client.privateGetPositions()['result']:
                        sleep(0.01)
                        
                        size = float(p['size'])
                        if p['side'] == 'sell':
                            size = size * -1
                        if size < 0:
                            direction = 'sell'
                        else:
                            direction = 'buy'

                        bbo     = self.get_bbo( p['future'] )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if direction == 'buy':
                            size = size
                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                        else:
                            if size < 0:
                                size = size * -1
                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
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
        print('Position total delta: ' + str(positionSize) + '$')
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
        print('Position exposure: ' + str(positionPos) + '$')
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

        gobreak = False
        breakfor = 0
        for k in self.vols.keys():
            if self.vols[k] > 10:
                gobreak = True
                breakfor = 0.25
                print('volatility high! taking 0.25hr break')
            if self.vols[k] > 10:
                gobreak = True
                breakfor = 0.5
                print('volatility high! taking 0.5hr break')
            if self.vols[k] > 15:
                gobreak = True
                breakfor = 1
                print('volatility high! taking 1hr break')
        if self.predict_1 * self.predict_5 > 0.9:
            gobreak = True
            print('volatility high! Taking 15m break!')
            breakfor = 0.15
        if self.predict_1 * self.predict_5 > 0.95:
            gobreak = True
            print('volatility high! Taking 1hr break!')
            breakfor = 1
        if self.predict_1 * self.predict_5 > 0.985:
            gobreak = True
            print('volatility high! Taking 4hr break!')
            breakfor = 4
        if gobreak == True:
            self.update_positions()
            self.cancelall()
            self.sls = self.sls + 1
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
            print('positionSize: ' + str(positionSize))
            size = size / len(self.client.privateGetPositions()['result'])
            print('size: ' + str(size))
            try:
                for p in self.client.privateGetPositions()['result']:
                    sleep(0.01)

                    bbo     = self.get_bbo( p['future'] )
                    bid_mkt = bbo[ 'bid' ]
                    ask_mkt = bbo[ 'ask' ]
                    mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                    if selling:

                        if 'ETH' in p['future']:
                            self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                
                        else:
                            self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                    else:

                        if 'ETH' in p['future']:
                            self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                        else:
                            self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
            except Exception as e:
                print(e)
            self.predict_5 = 0.5
            self.predict_1 = 0.5
            self.vols               = OrderedDict()
            sleep(60 * 60 * breakfor)

            #print( '\nMean Loop Time: %s' % round( self.mean_looptime, 2 ))
            #print( '' )
        for k in self.positions.keys():


            if 'size' in self.positions[k]:
                key = 'size'
                spot = self.get_eth()
            else:
                key = 'size'
                spot = self.get_spot()
            #print(self.positions[k][key])
            if self.positions[k]['size'] > 10:
                self.multsShort[k] = (self.positions[k]['size'] / 50) * POS_MOD
            if self.positions[k]['size'] < (-1 * 10 ):
                self.multsLong[k] = (-1 * self.positions[k]['size'] / 50) * POS_MOD
#Vols           
        print(' ')
        print(' ')
        print(' ')
        print(self.multsLong)
        print(self.multsShort)
    
    def place_orders( self ):

        if self.monitor:
            return None
        
        con_sz  = self.con_size        
        
        for fut in self.futures.keys():
            self.avg_pnl_sl_tp()
            account         = self.client.fetchBalance()

            spot            = self.get_spot()
            bal_btc         = float(account[ 'BTC' ] [ 'total' ]) * self.get_btc() / self.get_spot()
            print('bal btc ' + str(bal_btc))
            print('bal btc ' + str(bal_btc))
            print('bal btc ' + str(bal_btc))
            pos             = float(self.positions[ fut ][ 'size' ])
            pos_lim_long    = bal_btc * PCT_LIM_LONG / len(self.futures)
            pos_lim_short   = bal_btc * PCT_LIM_SHORT / len(self.futures)
            #print(pos_lim_long)
            #expi            = self.futures[ fut ][ 'expi_dt' ]
            #tte             = max( 0, ( expi - datetime.utcnow()).total_seconds() / SECONDS_IN_DAY )
            pos_decay       = 1.0 - math.exp( -DECAY_POS_LIM * 8035200 )
            pos_lim_long   *= pos_decay
            pos_lim_short  *= pos_decay
            pos_lim_long   -= pos
            pos_lim_short  += pos
            pos_lim_long    = max( 0, pos_lim_long  )
            pos_lim_short   = max( 0, pos_lim_short )
            
            #expi            = self.futures[ fut ][ 'expi_dt' ]
            ##print(self.futures[ fut ][ 'expi_dt' ])
            if self.eth is 0:
                self.eth = 200
            if 'ETH' in fut:
                if 'size' in self.positions[fut]:
                    pos             = self.positions[ fut ][ 'size' ] * self.eth  
                else:
                    pos = 0
            else:
                pos             = self.positions[ fut ][ 'size' ]

            #tte             = max( 0, ( expi - datetime.utcnow()).total_seconds() / SECONDS_IN_DAY )
            #pos_decay       = 1.0 - math.exp( -DECAY_POS_LIM * tte )
            #pos_lim_long   *= pos_decay
            #pos_lim_short  *= pos_decay
            

            pos_lim_long   -= pos
            pos_lim_short  += pos

            pos_lim_long    = max( 0, pos_lim_long  )
            pos_lim_short   = max( 0, pos_lim_short )

            min_order_size_btc = MIN_ORDER_SIZE / spot * CONTRACT_SIZE
            
            #yqbtc  = max( PCT_QTY_BASE  * bal_btc, min_order_size_btc)
            qtybtc  = PCT_QTY_BASE  * bal_btc 
            nbids   = min( math.trunc( pos_lim_long  / qtybtc ), MAX_LAYERS )
            nasks   = min( math.trunc( pos_lim_short / qtybtc ), MAX_LAYERS )
            positionSize = 0
            for p in self.positions:
                positionSize = positionSize + int(self.positions[p]['size'])

            #if 'PERP' in fut and self.thearb > 1 and positionSize < 0:
             #   nbids  = (nbids + (positionSize * -1)) # 30 / 10 = 3
            #    nbids = min(MAX_LAYERS * 1.5, nbids)
            print('fut ' + fut)
            print('bids ' + str(nbids))
            print('asks ' + str(nasks))
            

            print('fut ' + fut)
            print('bids ' + str(nbids))
            print('asks ' + str(nasks))    
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
            if fut == pair:
                print(' ')
                print('eps of perp before predictions: ' + str(eps))

            eps = eps * ((self.predict_1 * self.predict_5) * (self.predict_1 * self.predict_5))
            if fut == pair:
                print('eps after predictions: ' + str(eps))
                print(' ')
            riskfac     = math.exp( eps )

            if self.positionGains[fut] == True:
                bbo     = self.get_bbo( fut )
                bid_mkt = bbo[ 'bid' ]
                ask_mkt = bbo[ 'ask' ]
                mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                print('fut ' + fut)
                print(mid)
                mid_mkt = 0.5 * ( bid_mkt + ask_mkt )
                
                ords        = self.client.fetchOpenOrders( fut )
                cancel_oids = []
                bid_ords    = ask_ords = []
                if place_bids:
                    
                    bid_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                    
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    asks    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]

                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
            else:

                for p in self.client.privateGetPositions()['result']:
                    if pair.split('-')[0] in p['future']:
                        if p['entryPrice'] is not None:
                            avg = float(p['entryPrice'])
                bbo     = self.get_bbo( fut )
                bid_mkt = bbo[ 'bid' ]
                ask_mkt = bbo[ 'ask' ]
                mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                print('fut ' + fut)
                print(mid)
                mid_mkt = 0.5 * ( bid_mkt + ask_mkt )
                
                ords        = self.client.fetchOpenOrders( fut )
                cancel_oids = []
                bid_ords    = ask_ords = []
                if place_bids:
                    
                    bid_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    bids1    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]

                    bids1[ 0 ]   = ticksize_floor( bids1[ 0 ], tsz )
                    
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    asks1    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]

                    asks1[ 0 ]   = ticksize_ceil( asks1[ 0 ], tsz  )
                
                
                bbo     = self.getbidsandasks( fut , avg)
                bids = bbo['bids']
                asks = bbo['asks']
                asksn = []
                bidsn = []
                askso = asks
                bidso = asks
                if place_asks:
                    if len(asks1) >= 1:
                        asksn.append(asks1[0])
                        nasks = nasks + 1
                    if len(asks1) >= 2:
                        asksn.append(asks1[1])
                        nasks = nasks + 1
                    len_ask_ords    = min( len( ask_ords ), nasks )
                if len(askso) >= 1:
                    asksn.append(askso[0])
                if len(askso) >= 2:
                    asksn.append(askso[1])
                asks = asksn
                if place_bids:
                    if len(bids1) >= 1:
                        bidsn.append(bids1[0])
                        nbids = nbids + 1
                    if len(bids1) >= 2:
                        bidsn.append(bids1[1])
                        nbids = nbids + 1
                    len_bid_ords = min( len( bid_ords ), nbids )
                if len(bidso) >= 1:
                    bidsn.append(bidso[0])
                if len(bidso) >= 2:
                    asksn.append(bidso[1])
                print(bidsn)
                bids = bidsn
                ords        = self.client.fetchOpenOrders( fut )
                cancel_oids = []
                bid_ords    = ask_ords = []
                if place_bids:
                    
                    bid_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if (o[ 'side' ]).lower() == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
            for i in range( max( nbids, nasks )):
                sleep(0.01)
                # BIDS
                print('===')
                print('nbids')
                print(nbids)
                print(nasks)
                if place_bids and i < nbids:

                    if i > 0 and len(bids) > i:
                        prc = ticksize_floor( min( bids[ i ], bids[ i - 1 ] - tsz ), tsz )
                    else:
                        prc = bids[ 0 ]

                    qty = qtybtc   
                    print(qty)
                    if 4 in self.quantity_switch:
                        if self.diffdeltab[fut] > 0 or self.diffdeltab[fut] < 0:
                            qty = (qty / (self.diffdeltab[fut])) 
                    print(qty)
                    if 2 in self.quantity_switch:
                        qty =  ( qty * self.buysellsignal[fut])    
                    print(qty)
                    if 3 in self.quantity_switch:
                        qty =  (qty *self.multsLong[fut])   
                    print(qty)
                    if 1 in self.quantity_switch:
                        qty =  (qty / self.diff) 
                    print(qty)  
                    if qty < 0:
                        qty = qty * -1

                    positionSize = 0
                    for p in self.positions:
                        positionSize = positionSize + self.positions[p]['size']
                    print('-----')
                    print('-----')
                    print(fut)
                    print(self.positionGains[fut])

                    if 'PERP' in fut and self.thearb > 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures) 

                    elif 'PERP' not in fut and self.thearb > 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERP' not in fut and self.thearb < 1 and positionSize > 0:
                        qty = qty * 1.2#len(self.futures)
                    print(qty)
                    gogo = True
                    p1 = self.predict_1
                    p5 = self.predict_5
                    if p1 < 0.2:
                        p1 = 0.2
                    if p5 < 0.2:
                        p5 = 0.2
                    if fut == pair:
                        print(' ')
                        print('predict_1: ' + str(p1) + ' & predict_5: ' + str(p5))
                        print('qty of perp to buy before predictions: ' + str(qty))
                    #qty = round(qty * (1/(math.sqrt(p1)*math.sqrt(p5))) / 2)
                    if fut == 'BTC-26JUN20':
                        print('qty after predictions: ' + str(qty))
                        print(' ' )
                    positionSize = positionSize
                    #print('pos size: ' + str(positionSize))
                    if qty < 0:
                        qty = qty * -1
                    
                    if qty * 10 > self.maxqty:
                        self.maxqty = qty * 10
                        print('---')
                        print('self maxqty' + str(self.maxqty))
                    qtyold = qty
                    if positionSize < 0:
                        #len(self.futures)
                        if qtyold > qty:
                            qty = qtyold
                        if self.positionGains[fut] == True:
                            qty = qty * 1.25
                        else:
                            qty = qty * 0.25
                        
                        pps = 0
                        for p in self.positions:
                            pps = pps + self.positions[p]['size']
                        if pps  < 0:
                            ps = pps * -1
                        else:
                            ps = pps
                        ps = ps / len(self.futures) / 2
                        if ps < 1:
                            ps = 1
                        qty = ps

                        if qty > self.maxqty / 10 * 2.5 * 5:
                            if self.maxqty / 10 * 2.5 * 5 < ps:
                                qty = self.maxqty / 10 * 2.5 * 5
                            else:
                                qty = ps

                    print(qty)
                    if qty < self.futures[fut]['info']['sizeIncrement']:
                        qty = self.futures[fut]['info']['sizeIncrement']

                    print(qty)
                    if positionSize > 0:
                        print((qty * 10 * MAX_LAYERS) / 2 + positionSize)
                        print('maxqty: ' + str(self.maxqty))             
                        if (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2.5 * 5)):
                            if self.positions[fut]['size'] > 0:
                                print('max skew on buy')
                                len_bid_ords = 0
                                try:
                                    oid = bid_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except:
                                    abc123 = 1
                                gogo = False
                        if (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2.5 * 5 * 2)):
                            if self.positions[fut]['size'] < 0:
                                print('max skew on buy')
                                try:
                                    oid = bid_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except:
                                    abc123 = 1
                                len_bid_ords = 0
                                gogo = False
                    print(gogo)
                    if self.imselling[fut] == True:
                        print(fut + ' fut2 true fut btc perp gogo false buying')
                        gogo = False

                    if i < len_bid_ords and gogo == True:    

                        
                        try:
                            oid = bid_ords[ i ]['id']
                            side = bid_ords[ i ][ 'side' ]
                            self.client.editOrder( oid, fut, 'limit', side, qty, prc, {'leverage': 10})
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            try:

                                if self.arbmult[fut]['arb'] >= 1 and positionSize - qty /  2<= 0:
                                    self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                    try:
                                        oid = bid_ords[ i ]['id']
                                        cancel_oids.append( oid )
                                    except:
                                        abc123 = 1

                                if self.arbmult[fut]['arb'] <= 1 and  positionSize - qty /  2<= 0:
                                    self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                    try:
                                        oid = bid_ords[ i ]['id']
                                        cancel_oids.append( oid )
                                    except:
                                        abc123 = 1
                                #self.logger.warn( 'Edit failed for %s' % oid )
                            except (SystemExit, KeyboardInterrupt):
                                raise
                            except Exception as e:
                                print(e)
                                if pair in str(e) and i <= 1:
                                    try:

                                        positionSize = 0
                                        for p in self.positions:
                                            positionSize = positionSize + self.positions[p]['size']
                                        positionSize = positionSize
                                        if positionSize < 0:
                                            positionSize = positionSize * -1
                                        for k in self.arbmult:
                                            if (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2.5 * 5)) and self.positions[fut]['size'] > 0:
                                                len_bid_ords = 0
                                                try:
                                                    oid = bid_ords[ i ]['id']
                                                    cancel_oids.append( oid )
                                                except:
                                                    abc123 = 1
                                                print('max_skew on btc-perp buy!')
                                            elif (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2 * 1.25 * 5)) and self.positions[fut]['size'] < 0:
                                                len_bid_ords = 0
                                                try:
                                                    oid = bid_ords[ i ]['id']
                                                    cancel_oids.append( oid )
                                                except:
                                                    abc123 = 1
                                                print('max_skew on btc-perp buy!')    
                                            elif nbids > 0:
                                                if self.imselling[fut] == False:
                                                    if self.arbmult[k]['arb'] >= 1  or self.positions[fut]['size'] < 0:
                                                                                           
                                                        self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                    except Exception as e:
                                        print(e)
                                        #cancel_oids.append( oid )
                                        self.logger.warn( 'Bid order failed: %s bid for %s'
                                                % ( prc, qty ))

                    elif gogo == True:
                        print('self.imselling[BTC-PERP]')
                        print(self.imselling[pair])
                        print('self.imbuying[BTC-PERP]')
                        print(self.imbuying[pair])
                        #try:
                            #oid = bid_ords[ i ]['id']
                            #self.client.edit( oid, qty, prc )
                        #except Exception as e:
                            #print(bid_ords)
                            #abc = 1
                        try:
                            
                            if self.arbmult[fut]['arb'] >= 1 and positionSize - qty /  2<= 0:
                                self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                try:
                                    oid = bid_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except:
                                    abc123 = 1

                            if self.arbmult[fut]['arb'] <= 1 and positionSize - qty /  2<= 0:
                                self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                try:
                                    oid = bid_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except:
                                    abc123 = 1

                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            if pair in str(e) and i <= 1:
                                try:

                                    positionSize = 0
                                    for p in self.positions:
                                        positionSize = positionSize + self.positions[p]['size']
                                    positionSize = positionSize
                                    if positionSize < 0:
                                            positionSize = positionSize * -1
                                        
                                    for k in self.arbmult:
                                        if (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2.5 * 5)) and self.positions[fut]['size'] > 0:
                                            len_bid_ords = 0
                                            try:
                                                oid = bid_ords[ i ]['id']
                                                cancel_oids.append( oid )
                                            except:
                                                abc123 = 1
                                            print('max_skew on btc-perp buy!')
                                        elif (((qty * 10 * MAX_LAYERS) / 2 + positionSize > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize > self.maxqty * 2 * 1.25 * 5)) and self.positions[fut]['size'] < 0:
                                            len_bid_ords = 0
                                            try:
                                                oid = bid_ords[ i ]['id']
                                                cancel_oids.append( oid )
                                            except:
                                                abc123 = 1
                                            print('max_skew on btc-perp buy!')    
                                            
                                        elif nbids > 0:
                                            if self.imselling[fut] == False:
                                                if self.arbmult[k]['arb'] >= 1  or self.positions[fut]['size'] < 0:
                                                    self.client.createOrder(  fut, "limit", 'buy', qty, prc, {'leverage': 10})
                                
                                                    
                                except Exception as e:
                                    print(e)
                                    #cancel_oids.append( oid )
                                    self.logger.warn( 'Bid order failed: %s bid for %s'
                                                % ( prc, qty ))

                # OFFERS
                print('place_asks')
                print(place_asks)
                print('nasks')
                print(nasks)
                if place_asks and i < nasks:

                    if i > 0 and len(asks) > i:
                        prc = ticksize_ceil( max( asks[ i ], asks[ i - 1 ] + tsz ), tsz )
                    else:
                        prc = asks[ 0 ]
                        
                    qty = qtybtc   
                      
                    print(qty)
                    #print(qty)
                    #print(qty)
                    #print(qty)
                    if 4 in self.quantity_switch:
                        if self.diffdeltab[fut] > 0 or self.diffdeltab[fut] < 0:
                            qty = (qty / (self.diffdeltab[fut])) 
                    print(qty)
                    if 2 in self.quantity_switch:
                        qty =  ( qty / self.buysellsignal[fut])    
                    print(qty)
                    if 3 in self.quantity_switch:
                        qty =  (qty * self.multsShort[fut]) 
                        #print(qty)
                        #print(qty)
                        #print(qty)
                        #print(qty)
                    print(qty)
                    if 1 in self.quantity_switch:
                        qty =  (qty / self.diff)
                    print(qty)    
                    if qty < 0:
                        qty = qty * -1    

                    positionSize = 0
                    for p in self.positions:
                        positionSize = positionSize + self.positions[p]['size']

                    if 'PERP' in fut and self.thearb < 1 and positionSize < 0: 
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERP' not in fut and self.thearb < 1 and positionSize < 0:
                        qty = qty * 1.2#len(self.futures)
                    elif 'PERP' not in fut and self.thearb > 1 and positionSize > 0:
                        qty = qty * 1.2#len(self.futures)

                    print(qty)
                    gogo = True
                    p1 = self.predict_1
                    p5 = self.predict_5
                    if p1 < 0.2:
                        p1 = 0.2
                    if p5 < 0.2:
                        p5 = 0.2
                    if fut == 'BTC-26JUN20':
                        print(' ')
                        print('predict_1: ' + str(p1) + ' & predict_5: ' + str(p5))
                        print('qty of perp to sell before predictions: ' + str(qty))
                    #qty = round(qty * (1/(math.sqrt(p1)*math.sqrt(p5))) / 2)
                    positionSize = positionSize
                    if qty < 0:
                        qty = qty * -1
                    
                    if qty * 10 > self.maxqty:
                        self.maxqty = qty * 10
                        print('---')
                        print('self maxqty' + str(self.maxqty))
                    qtyold = qty
                    if positionSize > 0:
                        #len(self.futures)
                        if qtyold > qty:
                            qty = qtyold
                        if self.positionGains[fut] == True:
                            qty = qty * 1.25
                        else:
                            qty = qty * 0.25
                        
                        pps = 0
                        for p in self.positions:
                            pps = pps + self.positions[p]['size']
                        if pps  < 0:
                            ps = pps * -1
                        else:
                            ps = pps

                        ps = ps / len(self.futures) / 2
                        if ps < 1:
                            ps = 1
                        qty = ps
                        if qty > self.maxqty / 10 * 2.5 * 5:
                            if self.maxqty / 10 * 2.5 * 5 < ps:
                                qty = self.maxqty / 10 * 2.5 * 5
                            else:
                                qty = ps

                    print(qty)
                    if qty < self.futures[fut]['info']['sizeIncrement']:
                        qty = self.futures[fut]['info']['sizeIncrement']
                    print(qty)
                    #print('pos size: ' + str(positionSize))

                    if positionSize < 0:


                        print((qty * 10 * MAX_LAYERS) / 2 + positionSize * -1)
                        if (((qty * 10 * MAX_LAYERS) / 2 + positionSize * -1 > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize * -1 > self.maxqty * 2.5 * 5)) and self.positions[fut]['size'] < 0:
                            print('max skew on sell')
                            try:
                                oid = ask_ords[ i ]['id']
                                cancel_oids.append( oid )
                            except:
                                abc123 = 1
                            len_ask_ords = 0
                            gogo = False
                        if (((qty * 10 * MAX_LAYERS) / 2 + positionSize * -1 > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 + positionSize * -1 > self.maxqty * 2 * 1.25 * 5)) and self.positions[fut]['size'] > 0:
                            print('max skew on sell')
                            try:
                                oid = ask_ords[ i ]['id']
                                cancel_oids.append( oid )
                            except:
                                abc123 = 1
                            len_ask_ords = 0
                            gogo = False
                    if  self.imbuying[fut] == True:
                        print(fut + ' fut true fut btc perp gogo false selling')
                        gogo = False

                    if i < len_ask_ords and gogo == True: 
                        
                        try:
                            oid = ask_ords[ i ]['id']
                            side = ask_ords[ i ][ 'side' ]
                            self.client.editOrder( oid, fut, 'limit', side, qty, prc, {'leverage': 10})

                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            try:
                                if place_asks and i < nasks:
                                    if self.arbmult[fut]['arb'] >= 1 and positionSize + qty / 2>= 0:
                                        self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                        try:
                                            oid = ask_ords[ i ]['id']
                                            cancel_oids.append( oid )
                                        except:
                                            abc123 = 1
                                if self.arbmult[fut]['arb'] <= 1 and positionSize + qty / 2>= 0 and 'PERP' not in fut or self.arbmult[fut]['arb'] > 1 and 'PERP' in fut:
                                    self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                    try:
                                        oid = ask_ords[ i ]['id']
                                        cancel_oids.append( oid )
                                    except:
                                        abc123 = 1


                                #cancel_oids.append( oid )
                                #self.logger.warn( 'Sell Edit failed for %s' % oid )
                            except (SystemExit, KeyboardInterrupt):
                                raise
                            except Exception as e:
                                print(e)
                                if pair in str(e) and i <= 1:

                                    print('===')
                                    print(' ')
                                    print((qty * 10 * MAX_LAYERS) / 2 + positionSize)
                                    try:
                                        positionSize = 0
                                        for p in self.positions:
                                            positionSize = positionSize + self.positions[p]['size']
                                        positionSize = positionSize
                                        if positionSize < 0:
                                            positionSize = positionSize * -1
                                        
                                        for k in self.arbmult:
                                            print((qty * 10 * MAX_LAYERS) / 2 - positionSize)
                                            if (((qty * 10 * MAX_LAYERS) / 2 - positionSize > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 - positionSize > self.maxqty * 2.5 * 5)) and self.positions[fut]['size'] < 0:
                                                len_ask_ords = 0
                                                try:
                                                    oid = ask_ords[ i ]['id']
                                                    cancel_oids.append( oid )
                                                except:
                                                    abc123 = 1
                                                print('max_skew on btc-perp sell!')
                                            elif (((qty * 10 * MAX_LAYERS) / 2 - positionSize > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 - positionSize > self.maxqty * 2 * 1.25 * 5)) and self.positions[fut]['size'] > 0:
                                                len_ask_ords = 0
                                                try:
                                                    oid = ask_ords[ i ]['id']
                                                    cancel_oids.append( oid )
                                                except:
                                                    abc123 = 1
                                                print('max_skew on btc-perp sell!')  
                                                
                                            elif nasks > 0:
                                                print(self.imbuying[fut])
                                                if self.imbuying[fut] == False:
                                                    print(self.arbmult[k]['arb'] )
                                                    if self.arbmult[k]['arb'] <= 1  or self.positions[fut]['size'] > 0:
                                                        self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                                        
                                    except Exception as e:
                                        print(e)
                                       # cancel_oids.append( oid )
                                
                                       # self.logger.warn( 'Sell Edit failed for %s' % oid )
                                        self.logger.warn( 'Offer order failed: %s at %s'
                                                        % ( qty, prc ))
                                #cancel_oids.append( oid )


                    elif gogo == True:
                        
                        #try:
                            #oid = ask_ords[ i ]['id']
                            #self.client.edit( oid, qty, prc )
                        #except:
                            #print('edit error')
                            #abc = 1
                        try:
                            if self.arbmult[fut]['arb'] >= 1 and positionSize + qty / 2 >= 0:
                                self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                try:
                                    oid = ask_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except Exception as e:
                                    print (e)

                            if self.arbmult[fut]['arb'] <= 1 and positionSize + qty / 2 >= 0:
                                self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                try:
                                    oid = ask_ords[ i ]['id']
                                    cancel_oids.append( oid )
                                except Exception as e:
                                    print (e)
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            if pair in str(e) and i <= 1:
                                try:

                                    positionSize = 0
                                    for p in self.positions:
                                        positionSize = positionSize + self.positions[p]['size']
                                    positionSize = positionSize
                                    if positionSize < 0:
                                            positionSize = positionSize * -1
                                        
                                    for k in self.arbmult:
                                        print((qty * 10 * MAX_LAYERS) / 2 - positionSize)
                                        if (((qty * 10 * MAX_LAYERS) / 2 - positionSize > MAX_SKEW) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 - positionSize > self.maxqty * 2.5 * 5)) and self.positions[fut]['size'] < 0:
                                            len_ask_ords = 0
                                            try:
                                                oid = ask_ords[ i ]['id']
                                                cancel_oids.append( oid )
                                            except:
                                                abc123 = 1
                                            print('max_skew on btc-perp sell!')
                                        elif (((qty * 10 * MAX_LAYERS) / 2 - positionSize > MAX_SKEW * MAX_LAYERS) or (ULTRACONSERVATIVE == True and (qty * 10 * MAX_LAYERS) / 2 - positionSize > self.maxqty * 2 * 1.25 * 5)) and self.positions[fut]['size'] > 0:
                                            len_ask_ords = 0
                                            try:
                                                oid = ask_ords[ i ]['id']
                                                cancel_oids.append( oid )
                                            except:
                                                abc123 = 1
                                            print('max_skew on btc-perp sell!')  
                                            
                                        elif nasks > 0:
                                            print(self.imbuying[fut])
                                            if self.imbuying[fut] == False:
                                                print(self.arbmult[k]['arb'] ) 
                                                if self.arbmult[k]['arb'] <= 1  or self.positions[fut]['size'] > 0:
                                                    self.client.createOrder(  fut, "limit", 'sell', qty, prc, {'leverage': 10})
                                
                                                    

                                except Exception as e:
                                    print(e)
                                    #cancel_oids.append( oid )
                                    self.logger.warn( 'Offer order failed: %s at %s'
                                                % ( qty, prc ))
            print(bid_ords)
            if nbids < len( bid_ords ):
                cancel_oids += [ o['id'] for o in bid_ords[ nbids : ]]
            if nasks < len( ask_ords ):
                cancel_oids += [ o['id'] for o in ask_ords[ nasks : ]]

            for oid in cancel_oids:
                #print(oid)
                try:
                    self.client.cancelOrder( oid )
                except:
                    self.logger.warn( 'Order cancellations failed: %s' % oid )
                                        

    def restart( self ):        
        try:
            
            strMsg = 'RESTARTING'
            #print( strMsg )
            self.cancelall()
            strMsg += ' '
            for i in range( 0, 5 ):
                strMsg += '.'
                print( strMsg )
                sleep( 1 )
        except:
            pass
        finally:
            os.execv( sys.executable, [ sys.executable ] + sys.argv )        
    def randomword(self, length):
       letters = string.ascii_lowercase
       return ''.join(random.choice(letters) for i in range(length))
    def getbidsandasks(self, fut, mid_mkt):
        nbids = 2
        nasks = 2
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
        if fut == pair:
            print(' ')
            print('eps of perp before predictions: ' + str(eps))

        eps = eps * self.predict_1 * self.predict_5
        if fut == pair:
            print('eps after predictions: ' + str(eps))
            print(' ')
        riskfac     = math.exp( eps )
                

        
        
        bid0            = mid_mkt * math.exp( -MKT_IMPACT )
        bids    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]

        bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
        

        ask0            = mid_mkt * math.exp(  MKT_IMPACT )
        asks    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]

        asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
        return {'asks': asks, 'bids': bids}
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
                
                btclist.append(k)
            for k in ethlist:
                if 'PERP' not in k:
                    m = self.get_bbo(k)

                    bid = m['bid']
                    ask=m['ask']
                    bbo = self.get_bbo('ETH-PERP')
                    bid_mkt = bbo[ 'bid' ]
                    ask_mkt = bbo[ 'ask' ]
                    mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                    arb = bid/mid
                    if arb > 1:
                        self.arbmult[k]=({"arb": arb, "long": k[:3]+"-PERP", "short": k})
                    if arb < 1:
                        self.arbmult[k]=({"arb": arb, "long":k, "short": k[:3]+"-PERP"})

                    self.thearb = arb
                    print(self.arbmult)
            arbplus = 0
            for k in btclist:
                if 'PERP' not in k:
                    m = self.get_bbo(k)

                    bid = m['bid']
                    ask=m['ask']
                    
                    bbo = m
                    bid_mkt = bbo[ 'bid' ]
                    ask_mkt = bbo[ 'ask' ]
                    mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                    arb = bid/mid
                    if arb > 1.0004:
                        arbplus = arbplus + 1
                    if arb > 1:
                        
                        self.arbmult[k]=({"arb": arb, "long": k[:3]+"-PERP", "short": k})
                    
                    if arb < 1:
                        self.arbmult[k]=({"arb": arb, "long":k, "short": k[:3]+"-PERP"})
                    self.thearb = arb

                    print(self.arbmult)
            if arbplus != self.arbplus and self.arbplus != 0:
                print('kill all pos on arbplus != self.arbplus')
                
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
                    self.ohlcv[contract.replace('/', '')] = self.client.fetch_ohlcv(contract, '1m')
                    self.ohlcv[contract] = self.client.fetch_ohlcv(contract, '1m')
                
                self.update_timeseries()
                self.update_vols()
            if ( t_now - t_ts2 ).total_seconds() >= WAVELEN_TS2:
                t_ts2 = t_now
                #self.cancelall()

            self.avg_pnl_sl_tp()
            self.cancelorder = self.cancelorder - 1
            if self.cancelorder <= 0:
                self.cancelorder = 2
                #self.cancelall()
            positionSize = 0
            positionPos = 0

            positionPrices = {}
            positionPricesEth = {}

            
            for p in self.client.privateGetPositions()['result']:
                if pair.split('-')[0] in p['future']:
                    bbo     = self.get_bbo( p['future'] )
                    bid_mkt = bbo[ 'bid' ]
                    ask_mkt = bbo[ 'ask' ]
                    mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )

                    print(p['future'])
                    print(mid)
                    if p['entryPrice'] is not None:
                        print(float(p['entryPrice']))
                        if self.positions[p['future']]['size'] < 0:
                            self.positionGains[p['future']] = mid < float(p['entryPrice'])
                        else:
                            self.positionGains[p['future']] = mid > float(p['entryPrice'])
                        positionPrices[p['future']] = mid < float(p['entryPrice'])
                        positionPrices[p['future']] = mid > float(p['entryPrice'])
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] < 0:
                    positionPos = positionPos - self.positions[p]['size']
                else:   
                    positionPos = positionPos + self.positions[p]['size']
            buyPerp = False
            if pair in positionPrices:
                if positionPrices[pair] == False:
                    buyPerp = True
            print('buyperp ' + str(buyPerp))
            actuallyBuyingPerp = False
            if pair in self.positions:
                if self.positions[pair]['size'] > 0:
                    actuallyBuyingPerp = True
            print('actuallyBuyingPerp: ' + str(actuallyBuyingPerp))

            self.lastposdiff = self.posdiff #300
            self.posdiff = positionPos #400
            ts = 0
            ms = 0
            
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
        self.cancelall()
        self.logger = get_logger( 'root', LOG_LEVEL )
        # Get all futures contracts
        self.get_futures()

        for k in self.futures.keys():
            self.positionGains[k] = True
            self.imbuying[k] = False
            self.imselling[k] = False
            self.ohlcv[k.replace('/','')] = self.client.fetch_ohlcv(k, '1m')
            self.ohlcv[k] = self.client.fetch_ohlcv(k, '1m')

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
        account = self.client.fetchBalance()
        for p in self.client.privateGetPositions()['result']:
            try:
                pl = p['floatingPl']  / float(account[ 'BTC' ] [ 'total' ]) / spot 
                size = float(p['size'])
                if p['side'] == 'sell':
                    size = size * -1
                if size < 0:
                    direction = 'sell'
                else:
                    direction = 'buy'
               

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
            positionSize = 0
            positionPos = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] < 0:
                    positionPos = positionPos - self.positions[p]['size']
                else:   
                    positionPos = positionPos + self.positions[p]['size']
            if avg > TP and positionSize != 0:
                print('TP!')
                self.cancelall()
                self.tps = self.tps + 1
                
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('size: ' + str(size))
                try:
                    for p in self.client.privateGetPositions()['result']:
                        sleep(0.01)

                        bbo     = self.get_bbo( p['future'] )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if selling:
                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                            else:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                        else:
                            if 'ETH' in pair:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                

                except:
                    abc = 1
            positionSize = 0
            positionPos = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] < 0:
                    positionPos = positionPos - self.positions[p]['size']
                else:   
                    positionPos = positionPos + self.positions[p]['size']
            if avg < SL and positionSize != 0:
                print('SL! ' + str(avg))
                self.update_positions()
                self.cancelall()
                self.sls = self.sls + 1
                self.slsinarow = self.slsinarow + 1
                
                if self.slsinarow == 2:
                    print(' ')
                    print('two sls in a row!')
                    print(' ')
                    self.update_positions()
                    self.cancelall()
                    self.sls = self.sls + 1

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
                    print('positionSize: ' + str(positionSize))
                    size = size / len(self.client.privateGetPositions()['result'])
                    print('size: ' + str(size))
                    try:
                        for p in self.client.privateGetPositions()['result']:
                            sleep(0.01)

                            bbo     = self.get_bbo( p['future'] )
                            bid_mkt = bbo[ 'bid' ]
                            ask_mkt = bbo[ 'ask' ]
                            mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                            if selling:

                                if 'ETH' in p['future']:
                                    self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                
                                else:
                                    self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                            else:

                                if 'ETH' in p['future']:
                                    self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                else:
                                    self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                        sleep(60 * 0.5)
                    except Exception as e:
                        print(e)
                    sleep(60 * 0.5)
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('positionSize: ' + str(positionSize))
                size = size / len(self.client.privateGetPositions()['result'])
                print('size: ' + str(size))
                try:
                    for p in self.client.privateGetPositions()['result']:
                        sleep(0.01)

                        bbo     = self.get_bbo( p['future'] )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if selling:

                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'sell', size, mid * 0.98, {'leverage': 10})
                                

                        else:

                            if 'ETH' in p['future']:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                            else:
                                self.client.createOrder(  p['future'], "limit", 'buy', size, mid * 1.02, {'leverage': 10})
                                
                    sleep(60 * 0.5)
                except Exception as e:
                    print(e)
            else:
                self.slsinarow = 0
    
    def update_status( self ):
        account = self.client.fetchBalance()
        spot    = self.get_spot()
        print(account)
        self.equity_btc = float(account[ 'BTC' ] [ 'total' ])
        self.equity_usd = self.equity_btc * spot
        old1 = mmbot.predict_1
        old5 = mmbot.predict_5
        try:
            resp = requests.get('http://jare.cloud:8089/predictions').json()
            print(resp)
            if resp != 500:
                if '1m' in resp: 
                    mmbot.predict_1 = float(resp['1m'].replace('"',""))
                    mmbot.predict_5 = float(resp['5m'].replace('"',""))
                    if mmbot.predict_1 > 1:
                        mmbot.predict_1 = old1
                    if mmbot.predict_5 > 1:
                        mmbot.predict_5 = old5
                    if mmbot.predict_1 < 0:
                        mmbot.predict_1 = old1
                    if mmbot.predict_5 < 0:
                        mmbot.predict_5 = old5
                    print(' ')
                    print('New predictions!')
                    print('Predict 1m: ' + str(mmbot.predict_1))
                    print('Predict 5m:' + str(mmbot.predict_5))
                    print(' ')
        except Exception as e:
            print(e)
            mmbot.predict_1 = 0.5
            mmbot.predict_5 = 0.5
            abcd1234 = 1
        positionSize = 0
        positionPos = 0
        for p in self.positions:
            positionSize = positionSize + self.positions[p]['size']
            if self.positions[p]['size'] < 0:
                positionPos = positionPos - self.positions[p]['size']
            else:   
                positionPos = positionPos + self.positions[p]['size']
        account = self.client.fetchBalance()
        
        print('equity')
        print(self.equity_btc)
        self.update_positions()
        for k in self.positions.keys():

            self.multsShort[k] = 1
            self.multsLong[k] = 1
      #  self.deltas = OrderedDict( 
      #      { k: self.positions[ k ][ 'size' ] for k in self.futures.keys()}
      #  )
      
      #  self.deltas[ BTC_SYMBOL ] = float(account[ 'BTC' ] [ 'total' ]) / spot        
        
        
    def update_positions( self ):

        self.positions  = OrderedDict( { f: {
            'size':         0,
            'indexPrice':   None,
            'markPrice':    None
        } for f in self.futures.keys() } )
        positions       = self.client.privateGetPositions()['result']
        
        spot = self.get_spot()
        for pos in positions:
            print(pos)
            if pos[ 'future' ] in self.futures:
                if pos['side'] == 'sell':
                    pos['size'] = pos['size'] * spot * -1
                else:
                    pos['size'] = pos['size'] * spot
                self.positions[ pos[ 'future' ]] = pos
        print(self.positions)
        print(' ')
        print(' ')
        
    def update_positions2( self ):

        self.positions2  = OrderedDict( { f: {
            'size':         0,
            'size':      0,
            'indexPrice':   None,
            'markPrice':    None
        } for f in self.futures.keys() } )
        try:
            positions2       = self.client2.positions()
            
            for pos in positions2:

                if pos[ 'instrument' ] in self.futures:
                    self.positions2[ pos[ 'instrument' ]] = pos
        except:
            print('only one key, all good!')   
    def update_timeseries( self ):
        
        if self.monitor:
            return None
        
        for t in range( NLAGS, 0, -1 ):
            self.ts[ t ]    = cp.deepcopy( self.ts[ t - 1 ] )
        
        spot                    = self.get_spot()
        self.ts[ 0 ][ BTC_SYMBOL ]    = spot
        
        for contract in self.futures.keys():
            ob      = self.client.fetchOrderBook( contract )
            bids    = ob[ 'bids' ]
            asks    = ob[ 'asks' ]
            
            ords        = self.client.fetchOpenOrders( contract )
            bid_ords    = [ o for o in ords if (o[ 'side' ]).lower() == 'buy'  ]
            ask_ords    = [ o for o in ords if (o[ 'side' ]).lower() == 'sell' ]
            best_bid    = None
            best_ask    = None

            err = 10 ** -( self.get_precision( contract ) + 1 )
            
            for b in bids:
                match_qty   = sum( [ 
                    o['info']['size'] for o in bid_ords 
                    if math.fabs( b[0] - o['price'] ) < err
                ] )
                if match_qty < b[1]:
                    best_bid = b[0]
                    break
            
            for a in asks:
                match_qty   = sum( [ 
                    o['info']['size'] for o in ask_ords 
                    if math.fabs( a[0] - o['price'] ) < err
                ] )
                if match_qty < a[1]:
                    best_ask = a[0]
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
def marketThread(self, instrument, buyorsell, size):

    if self.marketthreading == False:
        self.marketthreading = True
        sleep(90)
        self.marketthreading = False
        bbo     = self.get_bbo( instrument )
        bid_mkt = bbo[ 'bid' ]
        ask_mkt = bbo[ 'ask' ]
        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
        #if buyorsell == 'buy':
        #    self.client.buy(  instrument, size, mid * 1.02, 'false' )
        #else:
        #    self.client.sell(  instrument, size, mid * 0.98, 'false' )                 
     

if __name__ == '__main__':
    
    try:
        mmbot = MarketMaker( monitor = args.monitor, output = args.output )

        mmbot.run()
        
    except( KeyboardInterrupt, SystemExit ):
        #print( "Cancelling open orders" )
        mmbot.cancelall()
        sys.exit()
    except Exception as e:
        print(e)
        print( traceback.format_exc())
        if args.restart:
            mmbot.restart()
        