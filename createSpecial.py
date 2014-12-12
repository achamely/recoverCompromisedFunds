#!/usr/bin/python
#Send Masterprotocol Currencies
import sys
import json
import time
import random
import hashlib
import operator
import commands
import pybitcointools
import os, decimal
import requests, urlparse
from pycoin import encoding
from ecdsa import curves, ecdsa

def is_pubkey_valid(pubkey):
    try:
        sec=encoding.binascii.unhexlify(pubkey)
        public_pair=encoding.sec_to_public_pair(sec)
        return curves.ecdsa.point_is_valid(ecdsa.generator_secp256k1, public_pair[0], public_pair[1])
    except TypeError:
        return False

def get_balance(address, csym, div):
    bal1=-3
    bal2=-4
    url =  'https://test.omniwallet.org/v1/address/addr/'
    PAYLOAD = {'addr': address }
    try:
        tx_data= requests.post(url, data=PAYLOAD, verify=False).json()
        for bal in tx_data['balance']:
            if csym == bal['symbol']:
                if div == 1:
                    bal1=('%.8f' % float(bal['value']))
                else:
                    fbal=float(bal['value'])/100000000
                    bal1=('%.8f' % fbal)
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        #print('Site 1 Unresponsive, Using 0 balance for now')
        bal1=-1

    url2 = 'https://www.masterchest.info/mastercoin_verify/adamtest.aspx?address='+address
    try:
        tx2_data=requests.get(url2, verify=False).json()
        for bal in tx2_data['balance']:
            if csym == bal['symbol']:
                bal2= ('%.8f' % float(bal['value']))
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        #print('Site 2 Unresponsive, Using 0 balance for now')
        bal2=-2

    if bal1 == bal2:
        #print(' Confirmed Balance of '+str(bal1)+' '+str(csym)+' for '+str(address)+' from 2 data points')
        return bal1
    elif bal1 > 0 and bal2 < 0:
        #print(' Balance mismatch, Site 1:['+str(bal1)+'] Site 2:['+str(bal2)+'] '+str(csym)+' for '+str(address)+' from 2 data points. Preffering Non Negative Balance Site 1: '+str(bal1))
        return bal1
    else:
        #print(' Balance mismatch, Site 1:['+str(bal1)+'] Site 2:['+str(bal2)+'] '+str(csym)+' for '+str(address)+' from 2 data points. Preffering Site 2: '+str(bal2))
        return bal2

if len(sys.argv) > 1 and "--force" not in sys.argv: 
    print "Takes a list of bitcoind options, addresses and a send amount and outputs a transaction in JSON \nUsage: cat send.json | python msc-sxsend.py\nRequires sx and a configured obelisk server"
    exit()

if "--force" in sys.argv:
    #WARNING: '--force' WILL STEAL YOUR BITCOINS IF YOU DON KNOW WHAT YOU'RE DOING
    force=True
else:
    force=False

JSON = sys.stdin.readlines()
try:
    listOptions = json.loads(str(''.join(JSON)))
except ValueError:
    print json.dumps({ "status": "NOT OK", "error": "Couldn't read input variables", "fix": "check input data"+str(JSON) })
    exit()

#get local running dir
RDIR=os.path.dirname(os.path.realpath(__file__))

#Define and make sure we have a data dir
DATA=RDIR+'/data/'
commands.getoutput('mkdir -p '+DATA)


#check if private key provided produces correct address
address = pybitcointools.privkey_to_address(listOptions['from_private_key'])
if not address == listOptions['transaction_from'] and not force:
    print json.dumps({ "status": "NOT OK", "error": "Private key does not produce same address as \'transaction from\'" , "fix": "Set \'force\' flag to proceed without address checks" })
    exit()

    private = listOptions['from_private_key']

#calculate minimum unspent balance (everything in satoshi's)
available_balance = int(0)

#BAL = commands.getoutput('sx balance -j '+listOptions['transaction_from'])
#try: 
#    balOptions = json.loads(str(''.join(BAL)))
#except ValueError:
#    print json.dumps({ "status": "NOT OK", "error": "Couldn't read/load available btc balance from sx", "fix": "check input data"+str(BAL) })
#    exit()

#available_balance = int(balOptions[0]['paid'])

broadcast_fee = int(10000)
output_minimum = int(5500) #dust threshold 5460

fee_total = broadcast_fee + (output_minimum * 4)

#check if minimum BTC balance is met
#if available_balance < fee_total and not force:
#    print json.dumps({ "status": "NOT OK", "error": "Not enough funds" , "fix": "Set \'force\' flag to proceed without balance checks" })
#    exit()

#get balance from  web interfaces
#if listOptions['currency_id'] == 1:
#    cid_balance=get_balance(listOptions['transaction_from'], 'MSC',2)
#elif listOptions['currency_id'] == 2:
#    cid_balance=get_balance(listOptions['transaction_from'], 'TMSC',2)
#else:
#    cid_balance=get_balance(listOptions['transaction_from'], 'SP'+str(listOptions['currency_id']),listOptions['property_type'])

#try:
#    float(cid_balance)
#except ValueError:
#    print json.dumps({"status": "NOT OK", "error": cid_balance , "fix": "Make sure Balance data is up to date: "})
#    exit()

#if  float(cid_balance) < float(listOptions['msc_send_amt']) and not force:
#    print json.dumps({"status": "NOT OK", "error": "Currency ID balance too low" , "fix": "Check Currency ID balance or set \'force\' flag to override: "+str(cid_balance)})
#    exit()

#generate public key of bitcoin address from priv key
#validated = commands.getoutput('sx get-pubkey '+listOptions['transaction_from'])
pubkey = commands.getoutput('echo '+listOptions['from_private_key']+' | sx pubkey')
if is_pubkey_valid(pubkey):
    pass
else:
    print json.dumps({ "status": "NOT OK", "error": "from address is invalid or hasn't been used on the network" , "fix": "Check from address or provide from address public key. Alternatively Set \'force\' flag to proceed without balance checks" })
    exit()

#don't need to get from block chain, we can use priv key to generate
#if "ddress" not in validated:
#    pubkey = validated
#elif is_pubkey_valid(listOptions['transaction_from_pubkey']):
#    pubkey =  commands.getoutput('echo '+listOptions['from_private_key']+' | sx pubkey')
#elif not force:
#    print json.dumps({ "status": "NOT OK", "error": "from address is invalid or hasn't been used on the network" , "fix": "Check from address or provide from address public key. Alternatively Set \'force\' flag to proceed without balance checks" })
#    exit()

#find largest spendable input from UTXO
#find a recent tx that has a balance more than msc send cost (4*.00005500 +.0001 = .00032220)
#todo, add ability to use multiple smaller tx to do multi input funding
#nws = (commands.getoutput('sx get-utxo '+listOptions['transaction_from']+" "+str(fee_total))).replace(" ", "")

#lsi_array=[]
#since sx doesn't provide a clean output we need to try and clean it up and get the usable outputs
#for x in nws.splitlines():
#  lsi_array.append(x.split(':'))

#z=0
tx_unspent_bal=0
utxo_list=[]
#for item in lsi_array:
#  if lsi_array[z][0] == "output":
#	utxo_list.append([lsi_array[z][1],lsi_array[z][2]])
#  if lsi_array[z][0] == "value":
#	tx_unspent_bal += int(lsi_array[z][1])
#  z += 1

utxo_list.append([listOptions['hashtospend'],listOptions['htsindex']])


#real stuff happens here:

# calculate change : 
# (total input amount) - (broadcast fee) - (total transaction fee)

change = int(tx_unspent_bal) - fee_total

#if change < 0 or fee_total > available_balance and not force:
#    print json.dumps({ "status": "NOT OK", "error": "Not enough funds" , "fix": "Send some btc to the sending address. Alternatively Set \'force\' flag to proceed without balance checks" })
#    exit()

if change < 0 :
  change = 0

#build multisig data address
from_address = listOptions['transaction_from']
transaction_type = 0   #simple send
sequence_number = 1    #packet number
#currency_id = 2        #MSC=1, TMSC=2
currency_id = int(listOptions['currency_id'])
#amount = int(float(listOptions['msc_send_amt'])*1e8)  #maran's impl used float??
#amount = int(decimal.Decimal(listOptions['msc_send_amt'])*decimal.Decimal("1e8"))
amount = int(listOptions['msc_send_amt'])

cleartext_packet = ( 
        (hex(sequence_number)[2:].rjust(2,"0") + 
            hex(transaction_type)[2:].rjust(8,"0") +
            hex(currency_id)[2:].rjust(8,"0") +
            hex(amount)[2:].rjust(16,"0") ).ljust(62,"0") )

sha_the_sender = hashlib.sha256(from_address).hexdigest().upper()[0:-2]
# [0:-2] because we remove last ECDSA byte from SHA digest

cleartext_bytes = map(ord,cleartext_packet.decode('hex'))  #convert to bytes for xor
shathesender_bytes = map(ord,sha_the_sender.decode('hex')) #convert to bytes for xor

msc_data_key = ''.join(map(lambda xor_target: hex(operator.xor(xor_target[0],xor_target[1]))[2:].rjust(2,"0"),zip(cleartext_bytes,shathesender_bytes))).upper()
#map operation that xor's the bytes from cleartext and shathesender together
#to obfuscate the cleartext packet, for more see Appendix Class B:
#https://github.com/faizkhan00/spec#class-b-transactions-also-known-as-the-multisig-method

obfuscated = "02" + msc_data_key + "00" 
#add key identifier and ecdsa byte to new mastercoin data key

invalid = True
while invalid:
    obfuscated_randbyte = obfuscated[:-2] + hex(random.randint(0,255))[2:].rjust(2,"0").upper()
    #set the last byte to something random in case we generated an invalid pubkey
    potential_data_address = pybitcointools.pubkey_to_address(obfuscated_randbyte)
    if bool(commands.getoutput('sx validaddr '+potential_data_address)):
        data_pubkey = obfuscated_randbyte
        invalid = False
#make sure the public key is valid using pybitcointools, if not, regenerate 
#the last byte of the key and try again

#### Build transaction
#retrieve raw transaction data to spend it and add it to the input 
validnextinputs=""
input_counter=0
#for utxo in utxo_list:
#   try:
#	prev_tx = json.loads(commands.getoutput('sx fetch-transaction '+utxo[0]+' | sx showtx -j'))
#   except ValueError:
#        print json.dumps({ "status": "NOT OK", "error": "Problem getting json format of utxo", "fix": "check utxo tx: "+str(utxo[0]) })
#        exit()
#
#   for output in prev_tx['outputs']:
#      if output['address'] == listOptions['transaction_from']:
#          validnextinputs+=str(" -i "+utxo[0]+":"+utxo[1])
#	  input_counter+=1


#manually tx will have 1 input, the tx we are creating before
utxo = utxo_list[0]
validnextinputs+=" -i "+str(utxo[0])+":"+str(utxo[1])
input_counter+=1


#validnextoutputs add the exodus address and the receipiant to the output
#If change is less than dust but greater than 0 send it to the receipiant: Bonus!
#to_fee=output_minimum
#if change < output_minimum and change > 0:
#    to_fee+=change
to_fee=output_minimum
if change > 0:
    to_fee+=change

validnextoutputs="-o 1EXoDusjGwvnjZUyKkxZ4UHEf77z6A5S4P:"+str(output_minimum)+" -o "+listOptions['transaction_to']+":"+str(to_fee)

#if there's any leftover change above dust send it back to yourself
#if change >= output_minimum: 
#    validnextoutputs+=" -o "+listOptions['transaction_from']+":"+str(change)

#create a temp file for the unsigned raw tx and the signed tx data for sx
#format: sender_address.recpt_address.secs_since_1970.random_hex
unsigned_raw_tx_file = DATA+listOptions['transaction_from']+'.'+listOptions['transaction_to']+'.'+commands.getoutput('date +%s')+'.'+hex(random.randint(0,255))[2:].rjust(2,"0")
signed_raw_tx_file = unsigned_raw_tx_file+'.signed'

#store the unsigned tx data in the file
commands.getoutput('sx mktx '+unsigned_raw_tx_file+' '+validnextinputs+' '+validnextoutputs)

#convert it to json for adding the msc multisig
try:
    json_tx = json.loads(commands.getoutput('cat '+unsigned_raw_tx_file+' | sx showtx -j'))
except ValueError:
    print json.dumps({ "status": "NOT OK", "error": "Problem getting json format of unsigned_raw_tx", "fix": "check filename: "+str(unsigned_raw_tx_file) })
    exit()

#add multisig output to json object
json_tx['outputs'].append({ "value": output_minimum*2, "script": "1 [ " + pubkey + " ] [ " + data_pubkey.lower() + " ] 2 checkmultisig", "addresses": "null"})

#construct byte arrays for transaction 
#assert to verify byte lengths are OK
version = ['01', '00', '00', '00' ]
assert len(version) == 4

num_inputs = [str(len(json_tx['inputs'])).rjust(2,"0")]
assert len(num_inputs) == 1

num_outputs = [str(len(json_tx['outputs'])).rjust(2,"0")]
assert len(num_outputs) == 1

sequence = ['FF', 'FF', 'FF', 'FF']
assert len(sequence) == 4

blocklocktime = ['00', '00', '00', '00']
assert len(blocklocktime) == 4

#prepare inputs data for byte packing
inputsdata = []
for _input in json_tx['inputs']:
    prior_out_str = _input['previous_output'].split(':')
    #prior_input_txhash = _input['previous_output'].upper()  
    prior_input_txhash = prior_out_str[0].upper()  
    #prior_input_index = str(prior_out_str[1]).rjust(2,"0").ljust(8,"0")
    prior_input_index = str(hex(int(prior_out_str[1]))[2: ]).rjust(2,"0").ljust(8,"0")
    input_raw_signature = commands.getoutput('sx fetch-transaction '+prior_out_str[0])

    prior_txhash_bytes =  [prior_input_txhash[ start: start + 2 ] for start in range(0, len(prior_input_txhash), 2)][::-1]
    assert len(prior_txhash_bytes) == 32

    prior_txindex_bytes = [prior_input_index[ start: start + 2 ] for start in range(0, len(prior_input_index), 2)]
    assert len(prior_txindex_bytes) == 4

    len_scriptsig = ['%02x' % len(''.join([]).decode('hex').lower())] 
    assert len(len_scriptsig) == 1
    
    inputsdata.append([prior_txhash_bytes, prior_txindex_bytes, len_scriptsig])

#prepare outputs for byte packing
output_hex = []
for output in json_tx['outputs']:
    value_hex = hex(int(float(output['value'])))[2:]
    value_hex = value_hex.rjust(16,"0")
    value_bytes =  [value_hex[ start: start + 2 ].upper() for start in range(0, len(value_hex), 2)][::-1]
    assert len(value_bytes) == 8

    scriptpubkey_hex = commands.getoutput('sx rawscript '+output['script'])
    scriptpubkey_bytes = [scriptpubkey_hex[start:start + 2].upper() for start in range(0, len(scriptpubkey_hex), 2)]
    len_scriptpubkey = ['%02x' % len(''.join(scriptpubkey_bytes).decode('hex').lower())]

    output_hex.append([value_bytes, len_scriptpubkey, scriptpubkey_bytes] )

#join parts into final byte array
hex_transaction = version + num_inputs

for _input in inputsdata:
    hex_transaction += (_input[0] + _input[1] + _input[2] + sequence)

hex_transaction += num_outputs

for output in output_hex:
    hex_transaction = hex_transaction + (output[0] + output[1] + output[2]) 

hex_transaction = hex_transaction + blocklocktime

#prepare and populate unsigned_raw_tx_file
phash = ''.join(hex_transaction).lower()
commands.getoutput('echo '+phash+' > '+unsigned_raw_tx_file)

#verify that transaction is valid
pht = commands.getoutput('echo '+phash+' | sx showtx -j')

try:
   fc = json.loads(pht)
except ValueError, e:
    # invalid json
    print json.dumps({ "status": "NOT OK", "error": "unsigned tx not valid/malformed: "+pht, "fix": "Check your inputs/json file"})
    exit()
else:
    pass # valid json

#We will now sign the first input using our private key.
PRIVATE_KEY = ''+listOptions['from_private_key']
PUBLIC_KEY=commands.getoutput('echo '+PRIVATE_KEY+' | sx pubkey')
DECODED_ADDR=commands.getoutput('echo '+PRIVATE_KEY+' | sx addr | sx decode-addr')
PREVOUT_SCRIPT=commands.getoutput('sx rawscript dup hash160 [ '+DECODED_ADDR+' ] equalverify checksig')

#Loop through and sign all the tx's inputs so we can create the final signed tx
x=0
commands.getoutput('cp '+unsigned_raw_tx_file+' '+unsigned_raw_tx_file+'.0')
while x < input_counter:
    y=x+1
    SIGNATURE=commands.getoutput('echo '+PRIVATE_KEY+' | sx sign-input '+unsigned_raw_tx_file+' '+str(x)+' '+PREVOUT_SCRIPT)
    SIGNATURE_AND_PUBKEY_SCRIPT=commands.getoutput('sx rawscript [ '+SIGNATURE+' ] [ '+PUBLIC_KEY+' ]')
    commands.getoutput('sx set-input '+unsigned_raw_tx_file+'.'+str(x)+' '+str(x)+' '+SIGNATURE_AND_PUBKEY_SCRIPT+' > '+unsigned_raw_tx_file+'.'+str(y))  # the first input has index 0
    x+=1

commands.getoutput('cp '+unsigned_raw_tx_file+'.'+str(y)+' '+signed_raw_tx_file)

tx_valid=commands.getoutput('sx validtx '+signed_raw_tx_file)

if "Success" not in tx_valid:
    print json.dumps({ "status": "NOT OK", "error": "signed tx not valid/failed sx validation: "+tx_valid, "fix": "Check your inputs/json file"})

try:
    tx_hash=json.loads(commands.getoutput('cat '+signed_raw_tx_file+' | sx showtx -j'))['hash']
except ValueError:
    print json.dumps({ "status": "NOT OK", "error": "Problem getting json format of signed_raw_tx_file", "fix": "check filename: "+str(signed_raw_tx_file) })
    exit()

#broadcast to obelisk node if requested
#if listOptions['broadcast'] == 1:
#    bcast_status=commands.getoutput('sx sendtx-obelisk '+signed_raw_tx_file)
#else:
#    bcast_status="out: Created, No TX"

#if listOptions['clean'] == 0:
#    pass
#elif listOptions['clean'] == 1:
#    x=0
#    while x <= input_counter:
#        commands.getoutput('rm '+unsigned_raw_tx_file+'.'+str(x))
#        x+=1
#elif listOptions['clean'] == 2:
x=0
commands.getoutput('rm '+unsigned_raw_tx_file)
while x <= input_counter:
        commands.getoutput('rm '+unsigned_raw_tx_file+'.'+str(x))
        x+=1
#elif listOptions['clean'] == 3:
#    commands.getoutput('rm '+unsigned_raw_tx_file)
#    commands.getoutput('rm '+unsigned_raw_tx_file+'.*')
#    signed_raw_tx_file='Cleaned/removed by request'


#return our final output
print json.dumps({ "valid_check": tx_valid.split(':')[1], "hash": tx_hash, "st_file": signed_raw_tx_file})
