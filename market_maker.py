# This code is for sample purposes only, comes as is and with no warranty or guarantee of performance

from collections    import OrderedDict
from datetime       import datetime
from os.path        import getmtime
from time           import sleep
from datetime import date, timedelta
from utils          import ( get_logger, lag, print_dict, print_dict_of_dicts, sort_by_key,
                             ticksize_ceil, ticksize_floor, ticksize_round )
import requests
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

args    = parser.parse_args()

KEY     = "Ef30Pt3-"#"VC4d7Pj1"
SECRET  = "TdREcHubAr4cPh-WwifNI0Y1iGdq3YjedsO-8ct-Fhw"#"IB4VEP26OzTNUt4JhNILOW9aDuzctbGs_K6izxQG2dI"
URL     = 'https://www.deribit.com'

        
BP                  = 1e-4      # one basis point
BTC_SYMBOL          = 'btc'
CONTRACT_SIZE       = 10        # USD
COV_RETURN_CAP      = 20       # cap on variance for vol estimate
DECAY_POS_LIM       = 0.1       # position lim decay factor toward expiry
EWMA_WGT_COV        = 4         # parameter in % points for EWMA volatility estimate
EWMA_WGT_LOOPTIME   = 0.1       # parameter for EWMA looptime estimate
FORECAST_RETURN_CAP = 100       # cap on returns for vol estimate
LOG_LEVEL           = logging.INFO
MIN_ORDER_SIZE      = 1
MAX_LAYERS          =  2        # max orders to layer the ob with on each side
MKT_IMPACT          =  0     # base 1-sided spread between bid/offer
NLAGS               =  2        # number of lags in time series
PCT                 = 100 * BP  # one percentage point

PCT_QTY_BASE        = 100       # pct order qty in bps as pct of acct on each order
MIN_LOOP_TIME       =   0.2       # Minimum time between loops
RISK_CHARGE_VOL     =  1	  # vol risk charge in bps per 100 vol
SECONDS_IN_DAY      = 3600 * 24
SECONDS_IN_YEAR     = 365 * SECONDS_IN_DAY
WAVELEN_MTIME_CHK   = 15        # time in seconds between check for file change
WAVELEN_OUT         = 15        # time in seconds between output to terminal
WAVELEN_TS          = 15        # time in seconds between time series update
VOL_PRIOR           = 100       # vol estimation starting level in percentage pts

EWMA_WGT_COV        *= PCT
MKT_IMPACT          *= BP

PCT_QTY_BASE        *= BP
VOL_PRIOR           *= PCT


class MarketMaker( object ):
    
    def __init__( self, monitor = True, output = True ):
        self.predict_1 = 0.5
        self.predict_5 = 0.5
        self.PCT_LIM_LONG        = 20       # % position limit long

        self.PCT_LIM_SHORT       = 20       # % position limit short
        self.MAX_SKEW = 1

        self.equity_usd         = None
        self.equity_btc         = None
        self.equity_usd_init    = None
        self.equity_btc_init    = None
        self.con_size           = float( CONTRACT_SIZE )
        self.client             = None
        self.maxMaxDD = 20
        self.minMaxDD = -8
        self.seriesData = {}
        self.seriesData[(datetime.strptime((date.today() - timedelta(days=1)).strftime('%Y-%m-%d'), '%Y-%m-%d'))] = 0
            
        self.startUsd = 0
        self.IM = 0
        self.LEV = 0
        self.tradeids = []
        self.amounts = 0
        self.fees = 0
        self.startTime = int(time.time()*1000)
        self.arbmult = {}

        self.deltas             = OrderedDict()
        self.futures            = OrderedDict()
        self.futures_prv        = OrderedDict()
        self.logger             = None
        self.mean_looptime      = 1
        self.monitor            = monitor
        self.output             = output or monitor
        self.positions          = OrderedDict()
        self.spread_data        = None
        self.this_mtime         = None
        self.ts                 = None
        self.vols               = OrderedDict()
    
    
    def create_client( self ):
        self.client = RestClient( KEY, SECRET, URL )
    
    def getbidsandasks(self, fut, mid_mkt):
        nbids = 2
        nasks = 2
        if self.positions[fut]['size'] < 0:
            normalize = 'asks'
        else:
            normalize = 'bids'
        tsz = self.get_ticksize( fut )            
        # Perform pricing
        vol = max( self.vols[ BTC_SYMBOL ], self.vols[ fut ] )
        eps = BP * vol * (RISK_CHARGE_VOL * (((self.predict_1 + self.predict_5) / 2) + 1))

        eps = eps * self.predict_1 * self.predict_5

        riskfac     = math.exp( eps )
                

        
        
        bid0            = mid_mkt * math.exp( -MKT_IMPACT )
        bids    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]
     

        bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
        

        ask0            = mid_mkt * math.exp(  MKT_IMPACT )
         
        asks    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]


        asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
        bbo = self.get_bbo(fut)
        if normalize == 'asks':
            ask0 = bbo['ask']
            asks    = [ ask0 * riskfac ** i for i in range( 1, int(nasks) + 1 ) ]


            asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
        else:
            bid0    =   bbo['bid']
            bids    = [ bid0 * riskfac ** -i for i in range( 1, int(nbids) + 1 ) ]
         

            bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
        return {'asks': asks, 'bids': bids, 'ask': asks[0], 'bid': bids[0]}
    
    def get_bbo( self, contract ): # Get best b/o excluding own orders
        
        # Get orderbook
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
        return { 'bid': best_bid, 'ask': best_ask }
    
        
    def get_futures( self ): # Get all current futures instruments
        
        self.futures_prv    = cp.deepcopy( self.futures )
        insts               = self.client.getinstruments()
        self.futures        = sort_by_key( { 
            i[ 'instrumentName' ]: i for i in insts  if i[ 'kind' ] == 'future' and 'BTC' in i['instrumentName']
        } )
        
        for k, v in self.futures.items():
            self.futures[ k ][ 'expi_dt' ] = datetime.strptime( 
                                                v[ 'expiration' ][ : -4 ], 
                                                '%Y-%m-%d %H:%M:%S' )
                        
        
    def get_pct_delta( self ):         
        self.update_status()
        return sum( self.deltas.values()) / self.equity_btc

    
    def get_spot( self ):
        return self.client.index()[ 'btc' ]

    
    def get_precision( self, contract ):
        return self.futures[ contract ][ 'pricePrecision' ]

    
    def get_ticksize( self, contract ):
        return self.futures[ contract ][ 'tickSize' ]
    
    
    def output_status( self ):
        
        if not self.output:
            return None
        
        self.update_status()
        
        now     = datetime.utcnow()
        days    = ( now - self.start_time ).total_seconds() / SECONDS_IN_DAY
        #print( '********************************************************************' )
        #print( 'Start Time:        %s' % self.start_time.strftime( '%Y-%m-%d %H:%M:%S' ))
        #print( 'Current Time:      %s' % now.strftime( '%Y-%m-%d %H:%M:%S' ))
        #print( 'Days:              %s' % round( days, 1 ))
        #print( 'Hours:             %s' % round( days * 24, 1 ))
        #print( 'Spot Price:        %s' % self.get_spot())
        
        
        pnl_usd = self.equity_usd - self.equity_usd_init
        pnl_btc = self.equity_btc - self.equity_btc_init
        
        #print( 'Equity ($):        %7.2f'   % self.equity_usd)
        #print( 'P&L ($)            %7.2f'   % pnl_usd)
        #print( 'Equity (BTC):      %7.4f'   % self.equity_btc)
        #print( 'P&L (BTC)          %7.4f'   % pnl_btc)
        #print( '%% Delta:           %s%%'% round( self.get_pct_delta() / PCT, 1 ))
        #print( 'Total Delta (BTC): %s'   % round( sum( self.deltas.values()), 2 ))        
        print_dict_of_dicts( {
            k: {
                'BTC': self.deltas[ k ]
            } for k in self.deltas.keys()
            }, 
            roundto = 2, title = 'Deltas' )
        
        print_dict_of_dicts( {
            k: {
                'Contracts': self.positions[ k ][ 'size' ]
            } for k in self.positions.keys()
            }, 
            title = 'Positions' )
        #print(self.positions)
        t = 0
        a = 0
        for pos in self.positions:
        
            a = a + math.fabs(self.positions[pos]['size'])
            t = t + self.positions[pos]['size']
            #print(pos + ': ' + str( self.positions[pos]['size']))

        #print('\nNet delta (exposure) BTC: $' + str(t))
        #print('Total absolute delta (IM exposure) BTC: $' + str(a))
        self.LEV = self.IM / 2
        

        #print('Actual initial margin across futs: ' + str(self.IM) + '% and leverage is (roughly)' + str(round(self.LEV * 1000)/1000) + 'x')
        #print('Max skew is: $' + str(self.MAX_SKEW * 10))

        if not self.monitor:
            print_dict_of_dicts( {
                k: {
                    '%': self.vols[ k ]
                } for k in self.vols.keys()
                }, 
                multiple = 100, title = 'Vols' )

            #print( '\nMean Loop Time: %s' % round( self.mean_looptime, 2 ))
            
        #print( '' )

        
    def place_orders( self ):

        if self.monitor:
            return None
        
        con_sz  = self.con_size        
        
        for fut in self.futures.keys():

            skew_size = 0
            #print('skew_size: ' + str(skew_size))
            #print(self.positions)
            for k in self.positions:
                skew_size = skew_size + self.positions[k]['size']
                #print('skew_size: ' + str(skew_size))
            psize = self.positions[fut]['size']
            

            if psize > 0:
                positionSkew = 'long'
                
            else:
                positionSkew = 'short' # 8 -40
            print('self.maxskew')
            print(self.MAX_SKEW)
            print('skew_size')
            print(skew_size)
            skewDirection = 'neutral'
            if skew_size  < -1 * self.MAX_SKEW / 3:
                skewDirection = 'short'
            if skew_size < -1 * self.MAX_SKEW / 3* 2:
                skewDirection = 'supershort'    
            if skew_size  >  self.MAX_SKEW /3:
                skewDirection = 'long'
            if skew_size  > self.MAX_SKEW /3 * 2:
                skewDirection = 'superlong'
            if psize < 0:
                psize = psize * -1
            account         = self.client.account()
            spot            = self.get_spot()
            bal_btc         = account[ 'equity' ] ## FIX THIS IN PROD
            pos             = self.positions[ fut ][ 'sizeBtc' ]
            for k in self.futures.keys():
                if self.arbmult[k]['short'] == 'others' and fut == self.arbmult[k]['long']:
                    self.PCT_LIM_LONG = self.PCT_LIM_LONG * 2
                    #print(fut + ' long double it')
                if self.arbmult[k]['long'] == 'others' and fut == self.arbmult[k]['short']:
                    self.PCT_LIM_SHORT = self.PCT_LIM_SHORT * 2 
                    #print(fut + ' short double it')   
            nbids = MAX_LAYERS
            nasks = MAX_LAYERS
            
            place_bids = True
            place_asks = True
            place_bids2 = True
            place_asks2 = True
            if self.IM > self.PCT_LIM_LONG:
                place_asks = False
                nbids = 0
            if self.IM > self.PCT_LIM_SHORT:
                place_bids = False
                nasks = 0
            if self.LEV > self.PCT_LIM_LONG / 2:
                place_asks2 = False
                nbids = 0
            if self.LEV > self.PCT_LIM_SHORT / 2:
                place_bids2 = False
                nasks = 0
            qtybtc  = PCT_QTY_BASE  * bal_btc
            #print('qtybtc: ' + str(qtybtc))

            #print('fut: ' + fut)
            nbids2 = MAX_LAYERS
            nasks2 = MAX_LAYERS
            
            place_bids2 = True
            place_asks2 = True
            if self.IM > self.PCT_LIM_LONG / 2:
                place_bids2 = False
                nbids2 = 0
            if self.IM > self.PCT_LIM_SHORT / 2:
                place_asks2 = False
                nasks2 = 0
            if self.LEV > self.PCT_LIM_LONG / 2 / 2:
                place_bids2 = False
                nbids2 = 0
            if self.LEV > self.PCT_LIM_SHORT / 2 / 2:
                place_asks2 = False
                nasks2 = 0
            #print('place_x2')
            #print(place_bids2)
            #print(place_asks2)
            #print(place_bids)
            #print(place_asks)

            overPosLimit = 'neither'
            if not place_bids2:
                overPosLimit = 'long'
            if not place_asks2:
                overPosLimit = 'short'
            if not place_bids:
                overPosLimit = 'superlong'
            if not place_bids:
                overPosLimit = 'supershort'
            positionGains = {}
            positionPrices = {}
            askMult = 1
            bidMult = 1
            for f in self.futures.keys():
                positionGains[f] = True
            for p in self.client.positions():
            
                if p['floatingPl'] > 0:
                    positionGains[p['instrument']] = True
                else:
                    positionGains[p['instrument']] = False
                positionPrices[p['instrument']] = p['averagePrice']    


            if not place_bids and not place_asks:
                #print( 'No bid no offer for ' + fut )
                continue
                
            tsz = self.get_ticksize( fut )            
            # Perform pricing
            vol = max( self.vols[ BTC_SYMBOL ], self.vols[ fut ] )
            if 'PERPETUAL' in fut:
                abc = 1
                ##print('Skew delta: ' + str(skew_size))
                ##print('RISK_CHARGE_VOL before AI: ' + str(RISK_CHARGE_VOL))
                ##print('RISK_CHARGE_VOL after AI: ' + str(RISK_CHARGE_VOL * ((self.predict_1 * self.predict_5) + 1)))
            eps         = BP * vol * (RISK_CHARGE_VOL * ((self.predict_1 * self.predict_5) + 1))
            riskfac     = math.exp( eps )

            bbo     = self.get_bbo( fut )
            bid_mkt = bbo[ 'bid' ]
            ask_mkt = bbo[ 'ask' ]
            
            if bid_mkt is None and ask_mkt is None:
                bid_mkt = ask_mkt = spot
            elif bid_mkt is None:
                bid_mkt = min( spot, ask_mkt )
            elif ask_mkt is None:
                ask_mkt = max( spot, bid_mkt )
            mid_mkt = 0.5 * ( bid_mkt + ask_mkt )
            
            ords        = self.client.getopenorders( fut )
            cancel_oids = []
            bid_ords    = ask_ords = []
            #print(fut)
            #print(fut)
            #print(fut)
            #print(fut)
            #print(fut)
            #print(fut)
            #print(fut)

            #print(positionSkew)
            #print(skewDirection)
            #print(overPosLimit)
            #print(place_asks)
            #print(positionGains[fut])
            # Long Position in Neutral Skew

            # # In Profit, Below Pos Limit

            print('fut: ' + fut)
            print('positionSkew: ' + positionSkew)
            print('skewDirection: ' + skewDirection)
            print('overPosLimit: ' + overPosLimit)
            print('positionGains[fut]: ' + str(positionGains[fut]))
        
            if positionSkew == 'long' and skewDirection == 'neutral' and positionGains[fut] == True and overPosLimit == 'neither':
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # At a loss, below pos limit

            elif positionSkew == 'long' and  ((skewDirection == 'short' or skewDirection == 'long') or (overPosLimit == 'short' or overPosLimit == 'long')) and positionGains[fut] == False:


                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    bids    = bbo['bids']
                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
                    asks    = bbo['asks']
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # profit or loss, at pos lim long

            elif positionSkew == 'long' and ((skewDirection == 'superlong' or skewDirection == 'supershort' ) or (overPosLimit == 'superlong' or overPosLimit == 'supershort')):
                bidMult = 0.5
                askMult = 0.5

                place_bids = False
                nbids = False
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # Long position in long skew

            # # in profit, <50% pos & skew
            elif positionSkew == 'long' and ((skewDirection == 'short' or skewDirection == 'long') or  place_bids2 == True) and positionGains[fut] == True:
                nbids = 0
                place_bids = False
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                askMult = 1.25

            # # at a loss, <50%
            elif positionSkew == 'long' and ((skewDirection == 'short' or skewDirection == 'long') or  place_bids2 == True) and positionGains[fut] == False:
                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    bids    = bbo['bids']
                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
                    asks    = bbo['asks']
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # in profit, >50%

            elif positionSkew == 'long' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_bids2 == False) and positionGains[fut] == True:
                
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                askMult = 1.5

            # # at a loss, >50%
            elif positionSkew == 'long' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_bids2 == False) and positionGains[fut] == False:
                
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # in profit, 100% pos or skew
            elif positionSkew == 'long' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_bids == False) and positionGains[fut] == True:
                place_bids = 0
                nbids = 0
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                askMult = 2
            # # at a loss, 100% pos or skew
            elif positionSkew == 'long' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_bids == False) and positionGains[fut] == False:
                
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                
            # Long position in short skew

            
            # # in profit, <50% pos & skew
            elif positionSkew == 'long' and ((skewDirection == 'short' or skewDirection == 'long') or  place_bids2 == True) and positionGains[fut] == True:
                bidMult = 1.25
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # at a loss, <50%
            elif positionSkew == 'long' and ((skewDirection == 'short' or skewDirection == 'long') or  place_bids2 == True) and positionGains[fut] == False:
                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    bids    = bbo['bids']
                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
                    asks    = bbo['asks']
                           
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # in profit, >50%

            elif positionSkew == 'long' and((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_bids2 == False) and positionGains[fut] == True:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                bidMult = 1.5

            # # at a loss, >50%
            elif positionSkew == 'long' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_bids2 == False) and positionGains[fut] == False:
                
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # in profit, 100% pos or skew
            elif positionSkew == 'long' and ((skewDirection == 'superlong' or skewDirection == '    ') or place_bids == False) and positionGains[fut] == True:
                place_bids = 0
                nbids = 0
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # at a loss, 100% pos or skew
            elif positionSkew == 'long' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_bids == False) and positionGains[fut] == False:
                nbids = 0
                place_bids = 0
                bidMult = 0.5
                askMult = 0.5
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            

            # SHORTS!

             # # In Profit, Below Pos Limit

            elif positionSkew == 'short' and skewDirection == 'neutral' and positionGains[fut] == True and overPosLimit == 'neither':
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # At a loss, below pos limit

            elif positionSkew == 'short' and ((skewDirection == 'short' or skewDirection == 'long') or (overPosLimit == 'short' or overPosLimit == 'long')) and positionGains[fut] == False :
 

                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    bids    = bbo['bids']
                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
                    asks    = bbo['asks']
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # profit or loss, at pos lim long

            elif positionSkew == 'short' and ((skewDirection == 'superlong' or skewDirection == 'supershort' ) or (overPosLimit == 'superlong' or overPosLimit == 'supershort')):


                place_asks = False
                nasks = False
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # Short position in long skew

            # # in profit, <50% pos & skew
            elif positionSkew == 'short' and ((skewDirection == 'short' or skewDirection == 'long') or  place_asks2 == True) and positionGains[fut] == True:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                askMult = 1.25

            # # at a loss, <50%
            elif positionSkew == 'short' and ((skewDirection == 'short' or skewDirection == 'long') or  place_asks2 == True) and positionGains[fut] == False:
                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    
                    bids    = bbo['bids']
                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    
                    asks    = bbo['asks']
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # in profit, >50%

            elif positionSkew == 'short' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_asks2 == False) and positionGains[fut] == True:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # at a loss, >50%
            elif positionSkew == 'short' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_bids2 == False) and positionGains[fut] == False:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # in profit, 100% pos or skew
            elif positionSkew == 'short' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_bids == False) and positionGains[fut] == True:
                place_asks = 0
                nasks = 0
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # at a loss, 100% pos or skew
            elif positionSkew == 'short' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_asks == False) and positionGains[fut] == False:
                nbids = 0
                place_bids = 0
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                
            # Short position in short skew

            
            # # in profit, <50% pos & skew
            elif positionSkew == 'short' and ((skewDirection == 'short' or skewDirection == 'long') or  place_asks2 == True) and positionGains[fut] == True:
                bidMult = 1.25
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # at a loss, <50%
            elif positionSkew == 'short' and ((skewDirection == 'short' or skewDirection == 'long') or  place_asks2 == True) and positionGains[fut] == False:
  
                bbo     = self.getbidsandasks( fut, positionPrices[fut] )
                bid_mkt = bbo[ 'bid' ]
                ask_mkt = bbo[ 'ask' ]
                #print(positionPrices[fut])
                #print(bid_mkt)
                #print(ask_mkt)
                if bid_mkt is None and ask_mkt is None:
                    bid_mkt = ask_mkt = spot
                elif bid_mkt is None:
                    bid_mkt = min( spot, ask_mkt )
                elif ask_mkt is None:
                    ask_mkt = max( spot, bid_mkt )
                mid_mkt = 0.5 * ( bid_mkt + ask_mkt )
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                #print(bids)
                #print(asks)
            # # in profit, >50%

            elif positionSkew == 'short' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_asks2 == False) and positionGains[fut] == True:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
                bidMult = 1.5

            # # at a loss, >50%
            elif positionSkew == 'short' and ((skewDirection == 'supershort' or skewDirection == 'superlong') or  place_asks2 == False) and positionGains[fut] == False:
                
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []

            # # in profit, 100% pos or skew
            elif positionSkew == 'short' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_asks == False) and positionGains[fut] == True:
                place_asks = 0
                nasks = 0
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bid0            = mid_mkt * math.exp( -MKT_IMPACT )
                    
                    bids    = [ bid0 * riskfac ** -i for i in range( 1, nbids + 1 ) ]

                    bids[ 0 ]   = ticksize_floor( bids[ 0 ], tsz )
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    ask0            = mid_mkt * math.exp(  MKT_IMPACT )
                    
                    asks    = [ ask0 * riskfac ** i for i in range( 1, nasks + 1 ) ]
                    
                    asks[ 0 ]   = ticksize_ceil( asks[ 0 ], tsz  )
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            # # at a loss, 100% pos or skew
            elif positionSkew == 'short' and ((skewDirection == 'superlong' or skewDirection == 'supershort') or place_asks == False) and positionGains[fut] == False:
                nasks = 0
                place_asks = 0
                if place_bids:
                
                    bid_ords        = [ o for o in ords if o[ 'direction' ] == 'buy'  ]
                    len_bid_ords    = min( len( bid_ords ), nbids )
                    bids = []
                    bids.append(bbo['bid'])

                    bids.append(bbo['bid'])
                else:
                    bids = []
                    len_bid_ords = 0
                    bid_ords = []
                if place_asks:
                    
                    ask_ords        = [ o for o in ords if o[ 'direction' ] == 'sell' ]    
                    len_ask_ords    = min( len( ask_ords ), nasks )
                    asks = []
                    asks.append(bbo['ask'])

                    asks.append(bbo['ask'])
                else:
                    asks = []
                    len_ask_ords = 0
                    ask_ords = []
            else:
                print('fut: ' + fut)
                print('positionSkew: ' + positionSkew)
                print('skewDirection: ' + skewDirection)
                print('overPosLimit: ' + overPosLimit)
                print('positionGains[fut]: ' + str(positionGains[fut]))
            #print(fut)
            print('place')
            if place_asks == True:
                len_ask_ords = 2
            if place_bids == True:
                len_bid_ords = 2
            print(place_bids)
            print(place_bids2)
            print(nbids)
            print(nbids2)

            self.execute_bids (fut, psize, skew_size, nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords, askMult, bidMult)    
            self.execute_offers (fut, psize, skew_size, nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords, askMult, bidMult)    
                                       
    def execute_bids ( self, fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords, askMult, bidMult):
       
        print('# BIDS')
        for i in range( max( nbids, nasks )):
            if place_bids and i < nbids:

                if i > 0:
                    prc = ticksize_floor( min( bids[ i ], bids[ i - 1 ] - tsz ), tsz )
                else:
                    prc = bids[ 0 ]

                #qty = ( prc * qtybtc / con_sz )  
                qty = self.equity_usd / 24  / 10 / 2
                max_bad_arb = int(self.MAX_SKEW / 3)
                print('qty: ' + str(qty))    
                print(max_bad_arb)
                qty = qty * bidMult
                qty = round(qty)                             
                
                if qty + skew_size >  self.MAX_SKEW:
                    print('bid self.MAX_SKEW return ...')
                    for xyz in bid_ords:
                        cancel_oids.append( xyz['orderId'] )

                    self.execute_cancels(fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords)
                        
                    return

                if i < len_bid_ords:    
                    print('i less')
                    try:
                        oid = bid_ords[ i ][ 'orderId' ]
                    
                        self.client.edit( oid, qty, prc )
                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except:
                        try:
                            if self.arbmult[fut]['arb'] > 1 and (self.positions[fut]['size'] - qty <= max_bad_arb / 3 * -1):
                                self.client.buy( fut, qty, prc, 'true' )
                                

                            if self.arbmult[fut]['arb'] < 1 :
                                self.client.buy(  fut, qty, prc, 'true' )

                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            self.logger.warn( 'Bid order failed: %s bid for %s'
                                            % ( prc, qty ))
                else:
                    try:
                        if self.arbmult[fut]['arb'] > 1 and (self.positions[fut]['size'] - qty <= max_bad_arb / 3 * -1):
                            self.client.buy( fut, qty, prc, 'true' )
                            

                        if self.arbmult[fut]['arb'] < 1 :
                            self.client.buy(  fut, qty, prc, 'true' )

                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except Exception as e:
                        print(e)
                        self.logger.warn( 'Bid order failed: %s bid for %s'
                                            % ( prc, qty ))

            self.execute_cancels(fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords)
                        
    def execute_offers ( self, fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords, askMult, bidMult):
        for i in range( max( nbids, nasks )):
       

            print('# OFFERS')

            if place_asks and i < nasks:

                if i > 0:
                    prc = ticksize_ceil( max( asks[ i ], asks[ i - 1 ] + tsz ), tsz )
                else:
                    prc = asks[ 0 ]
                    
                qty = self.equity_usd / 24  / 10 / 2

                max_bad_arb = int(self.MAX_SKEW / 3)
                print('qty: ' + str(qty))    
                print(max_bad_arb)
                

                qty = qty * askMult
                qty = round(qty)   
                #print('skew_size: ' + str(skew_size))
                #print('max_soew: ' + str(self.MAX_SKEW))
                if qty + skew_size * -1 >  self.MAX_SKEW:
                    #print('offer self.MAX_SKEW return ...')
                    for xyz in ask_ords:
                        cancel_oids.append( xyz['orderId'] )

                        
                    self.execute_cancels(fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords)
                    return
                if i < len_ask_ords:
                    
                    try:
                        oid = ask_ords[ i ][ 'orderId' ]
                    
                        self.client.edit( oid, qty, prc )
                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except:
                        try:
                            if self.arbmult[fut]['arb'] >= 1 :
                                self.client.sell( fut, qty, prc, 'true' )

                                
                            
                            if self.arbmult[fut]['arb'] <= 1 and self.positions[fut]['size'] + qty >= max_bad_arb / 3:
                                self.client.sell(  fut, qty, prc, 'true' )


                                
                        except (SystemExit, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            print(e)
                            self.logger.warn( 'Offer order failed: %s at %s'
                                            % ( qty, prc ))

                else:
                    try:
                        if self.arbmult[fut]['arb'] >= 1 :
                            self.client.sell( fut, qty, prc, 'true' )

                            
                        if self.arbmult[fut]['arb'] <= 1 and (self.positions[fut]['size'] + qty >= max_bad_arb / 3):
                            self.client.sell(  fut, qty, prc, 'true' )


                    except (SystemExit, KeyboardInterrupt):
                        raise
                    except Exception as e:
                        print(e)
                        self.logger.warn( 'Offer order failed: %s at %s'
                                            % ( qty, prc ))
        self.execute_cancels(fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords)
    def execute_cancels(self, fut, psize, skew_size,  nbids, nasks, place_bids, place_asks, bids, asks, bid_ords, ask_ords, qtybtc, con_sz, tsz, cancel_oids, len_bid_ords, len_ask_ords):
        if nbids < len( bid_ords ):
            cancel_oids += [ o[ 'orderId' ] for o in bid_ords[ nbids : ]]
        if nasks < len( ask_ords ):
            cancel_oids += [ o[ 'orderId' ] for o in ask_ords[ nasks : ]]
        for oid in cancel_oids:
            try:
                self.client.cancel( oid )
            except:
                self.logger.warn( 'Order cancellations failed: %s' % oid )
          
    def restart( self ):        
        try:
            strMsg = 'RESTARTING'
            print( strMsg )
            self.client.cancelall()
            strMsg += ' '
            for i in range( 0, 5 ):
                strMsg += '.'
                #print( strMsg )
                sleep( 1 )
        except:
            pass
        finally:
            os.execv( sys.executable, [ sys.executable ] + sys.argv )        
            

    def run( self ):
        
        self.run_first()
        self.output_status()
        
        t_ts = t_out = t_loop = t_mtime = datetime.utcnow()

        while True:

            self.get_futures()
            
            # Restart if a new contract is listed
            if len( self.futures ) != len( self.futures_prv ):
                self.restart()
            
            self.update_positions()
            bbo     = self.get_bbo( 'BTC-PERPETUAL' )
            bid_mkt = bbo[ 'bid' ]
            ask_mkt = bbo[ 'ask' ]
            mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
            bbos = []
            #self.client.buy(  'BTC-PERPETUAL', size, mid * 1.02, 'false' )
            for k in self.futures.keys():
                m = self.get_bbo(k)
                bid = m['bid']
                ask=m['ask']
                mid1 = 0.5 * (bid + ask)
                bbos.append({k: mid1 - self.get_spot()})

            #print(bbos)
            h = 0
            winner = ""
            positive = True
            for bbo in bbos:
                k = list(bbo.keys())[0]
                val = list(bbo.values())[0]
                if math.fabs(val) > h:
                    h = math.fabs(val)
                    winner = k
                    if val > 0:
                        positive = True
                    else:
                        positive = False
            if positive == True:
                for k in self.futures.keys():
                    if k == winner:
                        self.arbmult[winner]=({"arb": 1.5, "long": "others", "short": winner})
                    else:
                        self.arbmult[k]=({"arb": 0.5, "long": "others", "short": winner})
            else:
                for k in self.futures.keys():
                    if k == winner:
                        self.arbmult[winner]=({"arb": 0.5, "long": winner, "short": others})
                    else:
                        self.arbmult[k]=({"arb": 1.5, "long": winner, "short": "others"})
            skewingpos = 0
            skewingneg = 0
            positionSize = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] > 0:
                    skewingpos = skewingpos + 1
                elif self.positions[p]['size'] < 0:
                    skewingneg = skewingneg + 1
            print('pos size' + str(positionSize))
            print('skewing')
            print(skewingpos)
            print(skewingneg)
            print(self.MAX_SKEW)
            if positionSize is  0 and (skewingpos is 0 and skewingneg is 0):  
                print('0 on the dot 111!')
                print(self.arbmult)
                if self.MAX_SKEW != 1:
                    foundlong = ""
                    foundshort = ""
                    for k in self.futures.keys():
                        if self.arbmult[k]['short'] == 'others' and k == self.arbmult[k]['long']:
                            foundlong = k
                        if self.arbmult[k]['long'] == 'others' and k == self.arbmult[k]['short']:
                            foundshort = k  
                    print('foundlong: ' + foundlong)
                    print('foundshort: ' + foundshort)
                    for k in self.futures.keys():
                        print('k is '+ k)
                        bbo     = self.get_bbo( k )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if foundlong != "":
                            if k == foundlong:
                                print('k is foundlong')
                                self.client.buy(  foundlong, round(self.MAX_SKEW * 2)/ len(self.futures), mid * 1.02, 'false' )
                                
                            else:

                                print('k is not foundlong')
                                self.client.sell(  k, round(self.MAX_SKEW ) / len(self.futures), mid * 0.98, 'false' )
                        if foundshort != "":
                            if k == foundshort:
                                print('k is foundshort')
                                self.client.sell(  foundshort, round(self.MAX_SKEW  * 2)/ len(self.futures), mid * 0.98, 'false' )
                            else:

                                print('k is not foundshort')
                                self.client.buy(  k, round(self.MAX_SKEW ) / len(self.futures), mid * 1.02, 'false' )


            t_now   = datetime.utcnow()
            
            # Update time series and vols
            if ( t_now - t_ts ).total_seconds() >= WAVELEN_TS:
                t_ts = t_now
                self.update_timeseries()
                self.update_vols()
            sleep(0.01)
            size = int (100)
            
            
            self.place_orders()
            
            # Display status to terminal
            if self.output:    
                t_now   = datetime.utcnow()
                if ( t_now - t_out ).total_seconds() >= WAVELEN_OUT:
                    self.output_status(); t_out = t_now
            
            # Restart if file change detected
            t_now   = datetime.utcnow()
            if ( t_now - t_mtime ).total_seconds() > WAVELEN_MTIME_CHK:
                t_mtime = t_now
                if getmtime( __file__ ) > self.this_mtime:
                    self.restart()
            
            t_now       = datetime.utcnow()
            looptime    = ( t_now - t_loop ).total_seconds()
            
            # Estimate mean looptime
            w1  = EWMA_WGT_LOOPTIME
            w2  = 1.0 - w1
            t1  = looptime
            t2  = self.mean_looptime
            
            self.mean_looptime = w1 * t1 + w2 * t2
            
            t_loop      = t_now
            sleep_time  = MIN_LOOP_TIME - looptime
            if sleep_time > 0:
                time.sleep( sleep_time )
            if self.monitor:
                time.sleep( WAVELEN_OUT )

            
    def run_first( self ):
        
        self.create_client()
        self.client.cancelall()
        self.logger = get_logger( 'root', LOG_LEVEL )
        # Get all futures contracts
        self.get_futures()
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
    
    
    def update_status( self ):

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

        if gobreak == True:
            self.update_positions()
            self.client.cancelall()
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
            size = size / len(self.client.positions())
            print('size: ' + str(size))
            try:
                for p in self.client.positions():
                    sleep(0.01)

                    bbo     = self.get_bbo( p['instrument'] )
                    bid_mkt = bbo[ 'bid' ]
                    ask_mkt = bbo[ 'ask' ]
                    mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                    if selling:

                        if 'ETH' in p['instrument']:
                            self.client.sell(  p['instrument'], size, mid * 0.98, 'false' )
                        else:
                            self.client.sell(  p['instrument'], size, mid  * 0.98, 'false' )

                    else:

                        if 'ETH' in p['instrument']:
                            self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
                        else:
                            self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
            except Exception as e:
                print(e)
            self.predict_5 = 0.5
            self.predict_1 = 0.5
            self.vols               = OrderedDict()
            sleep(60 * 60 * breakfor)

        if self.startUsd != 0:
            startUsd = self.startUsd + self.startUsd2 
            nowUsd = self.equity_usd + self.equity_usd2
           
            


            diff = 100 * ((nowUsd / startUsd) -1)
            #print('diff')
            #print(diff)
            
            if diff < self.diff2:
                self.diff2 = diff
            if diff > self.diff3:
                self.diff3 = diff
            print('self diff2 : ' +str(self.diff2))
            print('self diff3 : ' +str(self.diff3))
            positionSize = 0
            for p in self.positions:
                positionSize = positionSize + self.positions[p]['size']
                if self.positions[p]['size'] > 0:
                    skewingpos = skewingpos + 1
                elif self.positions[p]['size'] < 0:
                    skewingneg = skewingneg + 1
            if self.diff3 > self.maxMaxDD and self.diff3 != 0:
                print('broke max max dd! sleep 24hr')
                self.client.cancelall()
                
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('size: ' + str(size))
                try:
                    for p in self.client.positions():
                        sleep(0.01)

                        bbo     = self.get_bbo( p['instrument'] )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if selling:
                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, mid * 0.98, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, mid * 0.98, 'false' )

                        else:
                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
                    sleep(60 * 11)
                except Exception as e:
                    print(e)
                time.sleep(60 * 60 * 24)

                self.diff3 = 0
                self.startUsd = self.equity_usd
            if self.diff2 < self.minMaxDD and self.diff2 != 0:
                print('broke min max dd! sleep 24hr')
                self.client.cancelall()
                
                if positionSize > 0:
                    selling = True
                    size = positionSize
                else:
                    selling = False
                    size = positionSize * -1
                print('size: ' + str(size))
                try:
                    for p in self.client.positions():
                        sleep(0.01)

                        bbo     = self.get_bbo( p['instrument'] )
                        bid_mkt = bbo[ 'bid' ]
                        ask_mkt = bbo[ 'ask' ]
                        mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
                        if selling:
                            if 'ETH' in p['instrument']:
                                self.client.sell(  p['instrument'], size, mid * 0.98, 'false' )
                            else:
                                self.client.sell(  p['instrument'], size, mid * 0.98, 'false' )

                        else:
                            if 'ETH' in p['instrument']:
                                self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
                            else:
                                self.client.buy(  p['instrument'], size, mid * 1.02, 'false' )
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


      
        try:
            if self.equity_btc_init != 0:
                for fut in self.futures.keys():
                    trades = self.client.tradehistory(1000, fut)
                    for t in trades:
                        timestamp = time.time() * 1000 - 24 * 60 * 60 * 1000
                        if t['timeStamp'] > self.startTime:
                        
                            if t['tradeId'] not in self.tradeids:
                                self.tradeids.append(t['tradeId'])
                                self.amounts = self.amounts + t['amount']
                                self.fees  = self.fees + (t['fee'])

                #print({'amounts': self.amounts, 'fees': self.fees, 'startTime': self.startTime, 'apikey': KEY, 'usd': self.equity_usd, 'btc': self.equity_btc, 'btcstart': self.equity_btc_init, 'usdstart': self.equity_usd_init})
                balances = {'amounts': self.amounts, 'fees': self.fees, 'startTime': self.startTime, 'apikey': KEY, 'usd': self.equity_usd, 'btc': self.equity_btc, 'btcstart': self.equity_btc_init, 'usdstart': self.equity_usd_init}
                resp = requests.post("http://jare.cloud:8080/subscribers", data=balances, verify=False, timeout=2)
                #print(resp)
        except:        
            abc = 123

        old1 = mmbot.predict_1
        old5 = mmbot.predict_5
        try:
            resp = requests.get('http://jare.cloud:8089/predictions').json()
            #print(resp)
            if resp != 500:
                if '1m' in resp: 
                    mmbot.predict_1 = float(resp['1m'].replace('"',"")) 
                    mmbot.predict_5 = float(resp['5m'].replace('"',"")) 
                   # if mmbot.predict_1 > 1:
                    #    mmbot.predict_1 = old1
                   # if mmbot.predict_5 > 1:
                   #     mmbot.predict_5 = old5
                    if mmbot.predict_1 < 0:
                        mmbot.predict_1 = old1
                    if mmbot.predict_5 < 0:
                        mmbot.predict_5 = old5
                    #print(' ')
                    #print('New predictions!')
                    #print('Predict 1m: ' + str(mmbot.predict_1))
                    #print('Predict 5m:' + str(mmbot.predict_5))
                    #print(' ')
        except Exception as e:
            print(e)
            mmbot.predict_1 = 0.5
            mmbot.predict_5 = 0.5
            abcd1234 = 1
        account = self.client.account()
        spot    = self.get_spot()

        self.equity_btc = account[ 'equity' ]
        #print(' ')
        #print(' ')
        #print('IM!')
        #print('IM!')
        #print('IM!')
        #print('IM!')
        #print('IM!')
        #print(account)
        self.IM = (account['initialMargin'] / account['equity'] * 100)
        self.IM = (round(self.IM * 1000) / 1000)
        self.equity_usd = self.equity_btc * spot
        self.MAX_SKEW = ((((0.017 - 0.01) / 0.005) * self.equity_usd) / 10) / 3

        self.update_positions()
                
        self.deltas = OrderedDict( 
            { k: self.positions[ k ][ 'sizeBtc' ] for k in self.futures.keys()}
        )
        self.deltas[ BTC_SYMBOL ] = account[ 'equity' ]        
        
        
    def update_positions( self ):

        self.positions  = OrderedDict( { f: {
            'size':         0,
            'sizeBtc':      0,
            'indexPrice':   None,
            'markPrice':    None
        } for f in self.futures.keys() } )
        positions       = self.client.positions()
        
        for pos in positions:
            if pos[ 'instrument' ] in self.futures:
                self.positions[ pos[ 'instrument' ]] = pos
        
    
    def update_timeseries( self ):
        
        if self.monitor:
            return None
        
        for t in range( NLAGS, 0, -1 ):
            self.ts[ t ]    = cp.deepcopy( self.ts[ t - 1 ] )
        
        spot                    = self.get_spot()
        self.ts[ 0 ][ BTC_SYMBOL ]    = spot
        
        for c in self.futures.keys():
            
            bbo = self.get_bbo( c )
            bid = bbo[ 'bid' ]
            ask = bbo[ 'ask' ]

            if not bid is None and not ask is None:
                mid = 0.5 * ( bbo[ 'bid' ] + bbo[ 'ask' ] )
            else:
                continue
            self.ts[ 0 ][ c ]               = mid
                
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
            dx  = x[ 0 ] / x[ 1 ] - 1
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
    except:
        print( traceback.format_exc())
        if args.restart:
            mmbot.restart()
        