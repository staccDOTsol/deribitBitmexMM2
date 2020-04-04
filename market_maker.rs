use std:: * ;

use curl::http;

use std::time::Duration;
use std::thread;
use std::io::{Error};
use deribit::models::{
    AuthRequest, BuyRequest, CancelByLabelRequest, CancelRequest, Currency, EditRequest,
    GetOpenOrdersByCurrencyRequest, GetOpenOrdersByInstrumentRequest, GetOrderStateRequest,
    SellRequest,
};
use deribit::DeribitBuilder;
use dotenv::dotenv;
use failure::{Error, Fallible};
use fluid::prelude::*;
use std::env::var;
use tokio::runtime::Runtime;
use tokio::time::delay_for;



use chrono::{DateTime, TimeZone, NaiveDateTime, Utc};



const key: String = "7x5cttEC".to_string()`;
const secret: String = "h_xxD-huOZOyNWouHh_yQnRyMkKyQyUv-EX96ReUHmM".to_string()`;
const URL: String = "https://www.deribit.com".to_string()`;
const BP: f64 = 0.0001;
const BTC_SYMBOL: String = "btc".to_string()`;
const CONTRACT_SIZE: f64 = 10.0;
const COV_RETURN_CAP: f64 = 100.0;
const DECAY_POS_LIM: f64 = 0.1;
const EWMA_WGT_LOOPTIME: f64 = 0.1;
const FORECAST_RETURN_CAP: f64 = 20.0;
const MIN_ORDER_SIZE: f64 = 1.0;
const MAX_LAYERS: f64 = 2.0;
const MKT_IMPACT: f64 = 0.5 * BP;
const NLAGS: i32 = 2;
const PCT: f64 = 100.0 * BP;
const EWMA_WGT_COV: f64 = 4.0 * PCT;
const PCT_LIM_LONG: f64 = 100.0 * PCT;
const MAX_SKEW: f64 = 1.0;
const PCT_LIM_SHORT: f64 = 100.0 * PCT;
const PCT_QTY_BASE: f64 = 100.0 * BP;
const MIN_LOOP_TIME: f64 = 0.2;
const RISK_CHARGE_VOL: f64 = 0.25;
const SECONDS_IN_DAY: f64 = 3600.0 * 24.0;
const SECONDS_IN_YEAR: f64 = 365.0 * SECONDS_IN_DAY;
const WAVELEN_MTIME_CHK: f64 = 15.0;
const WAVELEN_OUT: u64 = 15;
const WAVELEN_TS: f64 = 15.0;
const VOL_PRIOR: f64 = 100.0 * PCT;


		static predict_1: f64 = 0.5;
		static predict_5: f64 = 0.5;
		static equity_usd: f64 = 0.0;
		static equity_btc: f64 = 0.0;
		static equity_usd_init: f64 = 0.0;
		static equity_btc_init: f64 = 0.0;
		static con_size: f64 = 10.0;
		
		static mean_looptime: f64 = 1.0;
		static monitor: bool = false;
		static output: bool = true;
		
		static vols : ((),(),(),()) = ((),(),(),());

	static positions : ((),(),()) = ((),(),());
	static futures : ((),(),()) = ((),(),());
	static ts: ((),(),(),()) = ((),(),(),());
	fn get_bbo <  > (contract: String) -> (Option < f64 >, Option < f64 >)
	{
		

		let ob = client.getorderbook(contract);
		let bids = ob["bids"];
		let asks = ob["asks"];
		let ords = client.getopenorders(contract);
		let bid_ords = ords.iter().cloned().filter( | & o | o["direction"] == "buy").map( | o | o).collect:: < Vec < _ >> ();
		let ask_ords = ords.iter().cloned().filter( | & o | o["direction"] == "sell").map( | o | o).collect:: < Vec < _ >> ();
		let mut best_bid = None;
		let mut best_ask = None;
		let err = 10.0_f32.powf( -1_f32 *  ((futures.0).2) + 1_f32 );
		for b in bids
		{
			let fabs = (b["price"] - o["price"]);
			if fabs < 0.0 {
				fabs = 0_f32
			}
			let mut match_qty = bid_ords.iter().cloned().filter( | & o | fabs < err).map( | o | o["quantity"]).collect:: < Vec < _ >> ().iter().sum();
			if match_qty < b["quantity"]
			{
				best_bid = b["price"];
				break;
			}
		}
		for a in asks
		{
			let fabs = (b["price"] - o["price"]);
			if fabs < 0.0 {
				fabs = 0_f32
			}
			let mut match_qty = ask_ords.iter().cloned().filter( | & o | fabs < err).map( | o | o["quantity"]).collect:: < Vec < _ >> ().iter().sum();
			if match_qty < a["quantity"]
			{
				best_ask = a["price"];
				break;
			}
		}
		return (best_bid, best_ask);
	}
	fn get_futures(  ) -> Fallible<()> 
	{
		let drb = DeribitBuilder::default().build().unwrap();
	    let mut rt = Runtime::new()?;

	    let insts = async move {
	        let (mut client, _) = drb.connect().await?;
	        let req = GetInstrumentsRequest::new(Currency::BTC);
	        let _ = client.call(req).await?.await?;
	        let req = GetInstrumentsRequest::expired(Currency::ETH);
	        let _ = client.call(req).await?.await?;

	        Ok::<_, Error>(())
	    };
	    println(insts)
		let counter = 0
		for a in 0..futures.len() {
		    // Oops: `+ 1` makes sense for the integer, but not for the bool
		    println!("{}", data.a + 1); 
		}

		taken = ()
for a in 0..futures.len() {
    // Oops: `+ 1` makes sense for the integer, but not for the bool
for i in insts{
	let gogo = true
	for b in 0..taken.len() {
		if taken.b == i["instrumentName"]{
			gogo = false
		}
	}
        	if i["kind"] == "future" and "BTC" in i["instrumentName"] && gogo == true  {
        		taken.append(i["instrumentName"])
        	futures.a = (i["instrumentName"],i["tickSize"],["pricePrecision"],i["minTradeSize"],i["minTradeAmount"])
        	}
}

	}
}
	fn get_spot < F64 > (  ) -> f64
	{
		return client.index()["btc"];
	}

	
	fn output_status(  )
		{
			if !output
			{
				Err(None);
			}
			update_status();

			println!("{:?} {:?} ", "Spot Price: ", get_spot());
			let pnl_usd = equity_usd - equity_usd_init;
			let pnl_btc = equity_btc - equity_btc_init;
			println!("{:?} {:?} ", "Equity ($): ",equity_usd);
			println!("{:?} {:?} ", "P&L ($) ", pnl_usd);
			println!("{:?} {:?} ", "Equity (BTC) ", equity_btc);
			println!("{:?} {:?} ", "P&L (BTC) ", pnl_btc);

			for p in positions.keys(){
				println!("{:?} {:?}", p, positions[p]["size"])
			}

			if !monitor
			{
				for v in vols.keys(){
					println!("{:?} {:?}", v, vols[v])
				}
				println!("{:?} {:?}  ", "
					Mean Loop Time: ", mean_looptime);
				}
				println!(" ");
			}
			fn place_orders (   ) 
			{
				if monitor
				{
					Err(None);
				}
				let con_sz = con_size;
				for fut in futures.keys()
				{
					let mut skew_size = 0;
					for k in positions
					{
						skew_size = skew_size + positions[k]["size"];
					}
					let mut psize = positions[fut]["size"];
					if psize < 0
					{
						psize = psize * -1;
					}
					let account = client.account();
					let spot = get_spot();
					let bal_btc = account["equity"];
					let pos = positions[fut]["sizeBtc"];
					let mut pos_lim_long = bal_btc * PCT_LIM_LONG / futures.len().unwrap();
					let mut pos_lim_short = bal_btc * PCT_LIM_SHORT / futures.len().unwrap();

					let  pos_lim_long - pos_lim_long - pos;
					let pos_lim_short = pos_lim_short + pos;
					if pos_lim_long < 0.0 {
					let 	pos_lim_long = 0
					}
					if pos_lim_short < 0.0 {
						let pos_lim_short = 0
					}
					

					let min_order_size_btc = MIN_ORDER_SIZE / spot * CONTRACT_SIZE;
					let qtybtc = PCT_QTY_BASE  * bal_btc
					if min_order_size_btc > qtybtc{
						qtybtc = min_order_size_btc
					}
					let nbids = pos_lim_long  / qtybtc
					let nasks = pos_lim_short  / qtybtc
					if nbids < 0.0 {
						nbids = 0
					}
					if nasks < 0.0 {
						nasks = 0
					}
					if nbids > MAX_LAYERS{
						nbids = MAX_LAYERS
					}

					if nasks > MAX_LAYERS{
						nasks = MAX_LAYERS
					}
					
					let place_bids = nbids > 0;
					let place_asks = nasks > 0;
					if !place_bids && !place_asks
					{
						println!("{:?} {:?} {:?} ", "No bid no offer!", fut, math.trunc(pos_lim_long / qtybtc));
						continue;
					}
					let tsz = futures.0.1;
					let vol = vols[BTC_SYMBOL].iter().max().unwrap();
					if fut.iter().any( | & x | x == "PERPETUAL")
					{
						println!("RISK_CHARGE_VOL before AI: {:?} ", (RISK_CHARGE_VOL.to_string()));
						println!("RISK_CHARGE_VOL after AI: {:?} ", (RISK_CHARGE_VOL * predict_1 * predict_5 + 1.0)).to_string();
					}
					let eps = BP * vol * RISK_CHARGE_VOL * predict_1 * predict_5 + 1.0;
					let riskfac.powf(eps);
					let bbo = get_bbo(fut);
					let mut bid_mkt = bbo.0;
					let mut ask_mkt = bbo.1;
					if bid_mkt == None && ask_mkt == None
					{
						bid_mkt = spot;
					}
					else
					{
						if bid_mkt == None
						{
							bid_mkt = spot.iter().min().unwrap();
						}
						else
						{
							if ask_mkt == None
							{
								ask_mkt = spot.iter().max().unwrap();
							}
						}
					}
					let mid_mkt = 0.5 * bid_mkt + ask_mkt;
					let ords = client.getopenorders(fut);
					let cancel_oids = vec![];
					let mut bid_ords = vec![];
					if place_bids
					{
						let bid_ords = ords.iter().cloned().filter( | & o | o["direction"] == "buy").map( | o | o).collect:: < Vec < _ >> ();
						let len_bid_ords = bid_ords.len().unwrap();
						let bid0 = mid_mkt.powf(-(MKT_IMPACT));
						let mut bids = vec![];
						for i in 1.. nasks + 1 {
						bids.push(bid0 * riskfac.powf(i));
						}
						
						bids[0] = ticksize_floor(bids[0], tsz);
					}
					else
					{
						let bids = vec![];
						let len_bid_ords = 0;
						let bid_ords = vec![];
					}
					if place_asks
					{
						let ask_ords = ords.iter().cloned().filter( | & o | o["direction"] == "sell").map( | o | o).collect:: < Vec < _ >> ();
						let len_ask_ords = ask_ords.len().unwrap();
						let ask0 = mid_mkt.powf(MKT_IMPACT);

						let mut asks = vec![];
						for i in 1.. nasks + 1 {
						asks.push(ask0 * riskfac.powf(i));
						}
						asks[0] = ticksize_ceil(asks[0], tsz);
					}
					else
					{
						let asks = vec![];
						let len_ask_ords = 0;
						let ask_ords = vec![];
					}
					
let loop1 = nbids
				if nasks > nbids
				{
					let loop1 = nasks
				}
				for i in 0..loop1
				{
					if place_bids && i < nbids
					{
						if i > 0
						{
							let prc = ticksize_floor([bids[ i ], bids[ i - 1 ] - tsz].iter().min(), tsz);
						}
						else
						{
							let prc = bids[0];
						}
						let qty = (prc * qtybtc / con_sz).parse::<i32>;
						let MAX_SKEW = qty * 5.0;
						if psize + qty + skew_size > MAX_SKEW
						{
							println!("{:?} ", "bid max_skew return ...");
							for xyz in bid_ords
							{
								cancel_oids.append(xyz["orderId"]);
							}
							return;
						}
						if i < len_bid_ords
						{
							let oid = bid_ords[i]["orderId"];
							    let do_steps = || -> Result<(), Error> {
							        client.edit(oid, qty, prc)?;

							        Ok(())
							    };

							    if let Err(_err) = do_steps() {
							        client.buy(fut, qty, prc, "true");
									cancel_oids.append(oid);
							    }

							};
						}
						else
						{
								client.buy(fut, qty, prc, "true");

						}
					}
					let loop1 = nbids
				if nasks > nbids
				{
					let loop1 = nasks
				}
				for i in 0..loop1
				{
				
					if place_asks && i < nasks
					{
						if i > 0
						{
							let prc = ticksize_ceil([asks[ i ], asks[ i - 1 ] - tsz].iter().max(), tsz);
						}
						else
						{
							let prc = asks[0];
						}
						let qty = (prc * qtybtc / con_sz).parse::<i32>;
						let MAX_SKEW = qty * 5;
						if psize * -1.0 - qty - skew_size > -1.0 * MAX_SKEW
						{
							println!("{:?} ", "offer max_skew return ...");
							for xyz in ask_ords
							{
								cancel_oids.append(xyz["orderId"]);
							}
							return;
						}
						if i < len_ask_ords
						{
							let oid = ask_ords[i]["orderId"];
							let do_steps = || -> Result<(), Error> {
						        client.edit(oid, qty, prc)?;

						        Ok(())
						    };

						    if let Err(_err) = do_steps() {
						        client.sell(fut, qty, prc, "true");
								cancel_oids.append(oid);
						    }
							
						}
						else
						{
								client.sell(fut, qty, prc, "true");
							
						}
					}
				}
				unsafe {

				if nbids < bid_ords.len()
				{
					c = 0
					for o in bid_ords{
						if c > nbids{
							cancel_oids.append(o["orderId"])
						} 
						c+=1
					}
				}
				if nasks < ask_ords.len()
				{
					c = 0
					for o in ask_ords{
						if c > nasks{
							cancel_oids.append(o["orderId"])
						} 
						c+=1
					}
				}
			}
				for oid in cancel_oids
				{
						client.cancel(oid);
					
				}

							}
			}
			
			fn restart(  )
			{

					client.cancelall();
					
			}
			fn main(   )
			{
				run_first;
				output_status;
				let mut t_ts =  DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
				let mut t_out =  DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
				let mut t_loop =  DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
				let mut t_mtime = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
				loop
				{
					get_futures;
					
					update_positions;
					let mut t_now = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
					if t_now - t_ts.total_seconds() >= WAVELEN_TS
					{
						t_ts = t_now;
						update_timeseries;
						update_vols;
					}
					place_orders;
					if output
					{
						t_now = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
						if t_now - t_out.total_seconds() >= WAVELEN_OUT
						{
							output_status;
							t_out = t_now;
						}
					}
					t_now = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
					
					t_now = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
					let looptime = t_now - t_loop.total_seconds();
					let w1 = EWMA_WGT_LOOPTIME;
					let w2 = 1.0 - w1;
					let t1 = looptime;
					let t2 = mean_looptime;
					mean_looptime = w1 * t1 + w2 * t2;
					t_loop = t_now;
					let sleep_time = MIN_LOOP_TIME - looptime;
					if sleep_time > 0
					{
						thread::sleep(Duration::from_millis(sleep_time * 1000.0))
					}
					if monitor
					{

						thread::sleep(Duration::from_millis(WAVELEN_OUT * 1000))
					}
				}
			}
			fn run_first(   )-> Fallible<()>
			{
				create_client;
				client.cancelall();
				get_futures;
				
				

				let drb = DeribitBuilder::default()
			        .subscription_buffer_size(100000usize)
			        .build()
			        .unwrap();

			    let (mut client, mut subscription) = drb.connect().await?;

			    let req = PublicSubscribeRequest::new(&[
			        ("book.{:?}{:?} ", futures.0.instrumentName, ".raw").into(),
			         ("book.{:?}{:?} ", futures.1.instrumentName, ".raw").into(),
			         ("book.{:?}{:?} ", futures.2.instrumentName, ".raw").into(),
			        "deribit_price_index.btc_usd".into()
			    ]);

			    let _ = client.call(req).await?.await?;

			    client
			        .call(SetHeartbeatRequest::with_interval(30))
			        .await?
			        .await?;

			    while let Some(m) = subscription.next().await {
			        if let SubscriptionParams::Heartbeat {
			            r#type: HeartbeatType::TestRequest,
			        } = m?.params
			        {
			            client.call(TestRequest::default()).await?.await?;
			        }
			    }
				let symbols = vec![BTC_SYMBOL];
				for fut in futures.keys()
				{
					symbols.append(fut);
				}
				let ts_keys = symbols;
				
				let i = 0
				let tss = ()
				let volss = ()
				for s in symbols
				{
					tss.append(("instrument": s, "vol": VOL_PRIOR))
					volss.append(("instrument": s, "vol": VOL_PRIOR))
					let i +=1
				}
				let ts = tss
				let vols = volss
				start_time = DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc)
				update_status();
				equity_usd_init = equity_usd;
				equity_btc_init = equity_btc;
			}
			fn update_status(  )
				{
					let old1 = predict_1;
					let old5 = predict_5;
					let resp1 = http::handle()
					    .get("hhttp://jare.cloud:8089/predictions")
					    .exec().unwrap();

					  let resp = resp1.get_body();    
					    
							if resp != 500
							{
									predict_1 = (resp["1m"].replace('"', "")).parse::<f32>();
											predict_5 = (resp["5m"].replace('"', "")).parse::<f32>();
													if predict_1 < 0.0
													{
														predict_1 = old1;
													}
													if predict_5 < 0.0
													{
														predict_5 = old5;
													}
													println!("{:?} ", " "); 
													println!("{:?} ", "New predictions!"); 
													println!("Predict 1m: {:?} ", (predict_1).to_string()); 
													println!("Predict 5m: {:?} ", (predict_5).to_string()); 
													println!("{:?} ", " ");
											}

										let account = client.account();
										let spot = get_spot(); 
										let equity_btc = account["equity"]; 
										let equity_usd = equity_btc * spot;
										let PCT_LIM_LONG = 1.0 / equity_btc * 0.84;
										let PCT_LIM_SHORT = 1.0 / equity_btc * 0.84; 
										println!("relative pct qtys: {:?} ", (PCT_LIM_SHORT.to_string())); 
										update_positions(); 

									}
									fn update_positions(   )
									{
										let positions2 = client.positions();
										for pos in positions2
										{
											for counter2 in 0..futures.len() {
											    // Oops: `+ 1` makes sense for the integer, but not for the bool
												if futures.counter2.0 == pos["instrument"]{
													for counter3 in 0..positions.len() {
													    // Oops: `+ 1` makes sense for the integer, but not for the bool
														positions.counter3 = (pos["size"], pos["sizeBtc"], pos["instrument"]);
													}
												}
											}
										}
										}
									
									fn update_timeseries < RT, Option > (   ) ->  Result<RT, Option>
									{
										if monitor
										{
											Err(None);
										}
										let ts.1 = ts.0
										let ts.2 = ts.1
										let ts.3 = ts.2
										let spot = get_spot();
										let ts.0 = (BTC_SYMBOL, spot, DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc))
										
										for c in 0..2
										{
											let bbo = get_bbo(futures.c.instrumentName);
											let bid = bbo.0;
											let ask = bbo.1;
											if !bid == None && ask == None
											{
												let mid = 0.5 * bbo["bid"] + bbo["ask"];
											}
											else
											{
												continue;
											}
											let b = c + 1
											ts.b.append(futures.c.instrumentName, mid,  DateTime::<Utc>::from_utc(NaiveDateTime::from_timestamp(61, 0), Utc))
										}
									}
									fn update_vols < RT, Option > (   ) ->
									Result<RT, Option>
									{
										let w = EWMA_WGT_COV;
										let t = 0..NLAGS + 1. iter().map( | i | ts[i]["timestamp"]).collect:: < Vec < _ >> ();
										for c in vols.keys(){
											p[c] = None
										}
										for c in ts[0].keys()
										{
											p[c] = 0..NLAGS + 1. iter().map( | i | ts[i][c]).collect:: < Vec < _ >> ();
										}
										if any(t.iter().map( | x | x None None).collect:: < Vec < _ >> ())
										{
											Err(None);
										}
										for c in vols.keys()
										{
											if any(p[c].iter().map( | x | x None None).collect:: < Vec < _ >> ())
											{
												Err(None);
											}
										}
										let NSECS = SECONDS_IN_YEAR;
										let cov_cap = COV_RETURN_CAP / NSECS;
										for s in vols.keys()
										{
											let x = p[s];
											let dx = x[0] / x[1] - 1;
											let dt = t[0] - t[1].total_seconds();
											let mut v = dx.powf(2) / dt.iter().min().unwrap() * NSECS;
											v = w * v + 1 - w * vols[s].powf(2);
											vols[s] = math.sqrt(v);
										}
									}
