
var btc = 0;
const ccxt = require('ccxt')

var client = new ccxt.deribit(

            {"apiKey": process.env.KEY,
            "secret": process.env.SECRET
 })
var client2
if (process.env.KEY2.length > 2 ){
var client2 = new ccxt.deribit(

            {"apiKey": process.env.KEY2,
            "secret": -process.env.SECRET2
 })
}

/*
var client = new ccxt.deribit(

            {"apiKey": "VC4d7Pj1",
            "secret": "IB4VEP26OzTNUt4JhNILOW9aDuzctbGs_K6izxQG2dI"
 })

var client2 = new ccxt.deribit(

            {"apiKey": "5HkSPCwo",
            "secret": "z5fHc3FFB_SrVmEK6z0Unc-CjtHVU9_5pNMCdbXw_K0"
 })
 */
//client.urls['api'] = client.urls['test']
var usd2 = 0
var upnls = []
var rpnls = []
var tpnls = []
var btcstart
var usdstart
var btc4start
var usd4start
var usds = []
var usd4s = []
var prices = []
var btc4s = []
var btcs = []
var btc2 = 0
var usd4 = 0
var btc4 = 0
var ts = new Date().getTime()
var ids = []
var vol = 0
var line
var tradesArr = []
var first = true;
var m;
var lines = []
var fee = 0
var btcusd;
var upnl = 0;
var fees = []
var vols = []
var rpnl = 0;
var tss = []
var tpnl = 0;
setInterval(async function(){
	fee = 0;
	feecount = {}

	vol = 0;
	ethusd = await client.fetchTicker('ETH-PERPETUAL')
	ethusd = ethusd['last']
	btcusd = await client.fetchTicker('BTC-PERPETUAL')

btcusd = btcusd['last']
console.log(btcusd)
console.log(ethusd)
prices.push([new Date().getTime(), btcusd])
ethbtc = btcusd/ethusd

	if (first){
		m = await client.fetchMarkets()
	}
	for (var market in m){
		if (m[market].type == 'future'){
			var trades = await client.fetchMyTrades(m[market].symbol, undefined, 1000)
		
		d = new Date().getTime() - 1000 * 60 * 60 + (1000 * 60 * 60)
		d2 = new Date().getTime() - 1000 * 60 * 60 + (1000 * 60 * 60)
		
	for(var t in trades){
		if (trades[t].timestamp > d && trades[t].timestamp < d2 ){
			if (feecount[m[market].symbol] == undefined){
		feecount[m[market].symbol] = 0
	}


		vol+=(trades[t].amount)

			feecount[m[market].symbol] += 1
		if (trades[t].fee.currency == 'ETH'){
fee+=(trades[t].fee.cost) / (ethbtc)
		}else {
		fee+=(trades[t].fee.cost)
	}
	}
/* if(trades[t].side == 'sell'){
lines.push([
        '#FF0000', // Red
        '1',
        trades[t].timestamp.toString() // Position, you'll have to translate this to the values on your x axis
    ]
)
}
else {
lines.push([
        '#00FF00', // Red
        '1',
        trades[t].timestamp.toString() // Position, you'll have to translate this to the values on your x axis
    ]
)
}
line = lines[lines.length-1]
*/
tradesArr.push(trades[t].id)
	}
	
	}
	}
	console.log(feecount)
	fees.push(fee)
	vols.push(vol)
	////console.log(trades.length)

////console.log(account)
account         = await client.fetchBalance()
////console.log(account)
upnl = (account.info.result.session_upl)
rpnl =account.info.result.session_rpl
tpnl = account.info.result.total_pl
tpnls.push(tpnl)
rpnls.push(rpnl)
upnls.push(upnl)
btc = parseFloat(account [ 'info' ] ['result']['equity'])
account         = await client.fetchBalance({'currency':'ETH'})
console.log(btc)
console.log(ethbtc)
btc += parseFloat(account [ 'info' ] ['result']['equity']) / ethbtc
btc3 = 0
if (process.env.KEY2.length > 2){
account2         = await client2.fetchBalance()
////console.log(account)

btc3 = parseFloat(account2 [ 'info' ] ['result']['equity'])
account2         = await client2.fetchBalance({'currency':'ETH'})

btc3 += parseFloat(account2[ 'info' ] ['result']['equity']) / ethbtc
console.log(btc)
}
if (btc3 > 0){
btc2 = btc + btc3
}
else {
	btc2 = btc
}
btc4 = btc
usd4 = btc4 * btcusd
usd2 = btc2 * btcusd
console.log(btc2)
if (first)
{
	btc4start = btc2
	usd4start = btc2 * btcusd
btcstart = btc2
first = false;
usdstart = btcstart * btcusd
}
if (btc != 0 && btc2 != 0){
	ts = (new Date().getTime())
	tss.push(ts)
	usds.push( [new Date().getTime(), -1 * (1-(usd2 / usdstart)) * 100])

btcs.push( [new Date().getTime(), -1 * (1-(btc2 / btcstart)) * 100])
	usd4s.push( [new Date().getTime(), -1 * (1-(usd4 / usd4start)) * 100])

btc4s.push( [new Date().getTime(), -1 * (1-(btc4 / btc4start)) * 100])
}
////console.log(btc)
}, 5500)

const express = require('express');
var cors = require('cors');
var app = express();
app.use(cors());
var request = require("request")
var bodyParser = require('body-parser')
app.set('view engine', 'ejs');
app.listen(process.env.PORT || 80, function() {});
app.get('/update', cors(), (req, res) => {

    res.json({btc: [new Date().getTime(), -1 * (1-(btc2 / btcstart)) * 100], 
    	btcusd: [new Date().getTime(), btcusd], 
    	usd: [new Date().getTime(), -1 * (1-(usd2 / usdstart)) * 100],

    	 qty: vol * 10, line:line, fee:fee * btcusd, rpnl: rpnl, upnl: upnl, tpnl: tpnl, ts: ts})

})

app.get('/', (req, res) => {
        res.render('index.ejs', {
            btc: btcs, lines:lines,
            usd: usds,
            rpnls: rpnls,
            upnls: upnls,
            vols: vols,
            fees: fees,
            tpnls: tpnls,
            tss: tss,
            btcusd: prices
        })

});
