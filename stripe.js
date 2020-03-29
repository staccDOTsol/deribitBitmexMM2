// This example uses Express to receive webhooks
const app = require('express')();

// Use body-parser to retrieve the raw body as a buffer
const bodyParser = require('body-parser');

// Match the raw body to content type application/json
app.post('/subscribed', bodyParser.raw({type: 'application/json'}), (request, response) => {
  let event;

  try {
    event = JSON.parse(request.body);
  } catch (err) {
    response.status(400).send(`Webhook Error: ${err.message}`);
  }

  // Handle the event
  if(event.type.indexOf('charge') != -1){
  if (event.data.object.outcome.network_status == 'approved_by_network'){

    console.log('payment outcome approved by network, we\'d now proceed to spin a VM for: ')
    console.log(event.data.object.billing_details)
    let string = event.data.object.description.split('\\n')
    console.log('key2: ' + string[0])
    console.log('secret2: ' + string[1])
    console.log('key: ' + string[2])
    console.log('secret: ' + string[3])
  }
}else {
  console.log(event.data)
}
      // Unexpected event type
      return response.status(200).end();
  

  // Return a response to acknowledge receipt of the event
  response.json({received: true});
});

app.listen(8088, () => console.log('Running on port 8000'));
