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

BAL = commands.getoutput('sx balance -j '+listOptions['transaction_from'])
try: 
    balOptions = json.loads(str(''.join(BAL)))
except ValueError:
    print json.dumps({ "status": "NOT OK", "error": "Couldn't read/load available btc balance from sx", "fix": "check input data"+str(BAL) })
    exit()

available_balance = int(balOptions[0]['paid'])

broadcast_fee = int(10000)
output_minimum = int(5500) #dust threshold 5460

fee_total = (broadcast_fee*2) + (output_minimum * 4)

#check if minimum BTC balance is met
if available_balance < fee_total and not force:
    print json.dumps({ "status": "NOT OK", "error": "Not enough funds" , "fix": "Set \'force\' flag to proceed without balance checks" })
    exit()


#generate public key of bitcoin address from priv key
#validated = commands.getoutput('sx get-pubkey '+listOptions['transaction_from'])
pubkey = commands.getoutput('echo '+listOptions['from_private_key']+' | sx pubkey')
if is_pubkey_valid(pubkey):
    pass
else:
    print json.dumps({ "status": "NOT OK", "error": "from address is invalid or hasn't been used on the network" , "fix": "Check from address or provide from address public key. Alternatively Set \'force\' flag to proceed without balance checks" })
    exit()

#find largest spendable input from UTXO
#find a recent tx that has a balance more than msc send cost (4*.00005500 +.0001 = .00032220)
#todo, add ability to use multiple smaller tx to do multi input funding
nws = (commands.getoutput('sx get-utxo '+listOptions['transaction_from']+" "+str(fee_total))).replace(" ", "")

lsi_array=[]
#since sx doesn't provide a clean output we need to try and clean it up and get the usable outputs
for x in nws.splitlines():
  lsi_array.append(x.split(':'))

z=0
tx_unspent_bal=0
utxo_list=[]
for item in lsi_array:
  if lsi_array[z][0] == "output":
	utxo_list.append([lsi_array[z][1],lsi_array[z][2]])
  if lsi_array[z][0] == "value":
	tx_unspent_bal += int(lsi_array[z][1])
  z += 1

#real stuff happens here:

# calculate change : 
# (total input amount) - (broadcast fee) - (total transaction fee)

change = int(tx_unspent_bal) - fee_total

if change < 0 or fee_total > available_balance and not force:
    print json.dumps({ "status": "NOT OK", "error": "Not enough funds" , "fix": "Send some btc to the sending address. Alternatively Set \'force\' flag to proceed without balance checks" })
    exit()

#build multisig data address
from_address = listOptions['transaction_from']

#### Build transaction
#retrieve raw transaction data to spend it and add it to the input 
validnextinputs=""
input_counter=0
for utxo in utxo_list:
   try:
	prev_tx = json.loads(commands.getoutput('sx fetch-transaction '+utxo[0]+' | sx showtx -j'))
   except ValueError:
        print json.dumps({ "status": "NOT OK", "error": "Problem getting json format of utxo", "fix": "check utxo tx: "+str(utxo[0]) })
        exit()

   for output in prev_tx['outputs']:
      if output['address'] == listOptions['transaction_from']:
          validnextinputs+=str(" -i "+utxo[0]+":"+utxo[1])
	  input_counter+=1

#validnextoutputs add the exodus address and the receipiant to the output
#If change is less than dust but greater than 0 send it to the receipiant: Bonus!
to_fee=fee_total-broadcast_fee
if change < output_minimum and change > 0:
    to_fee+=change

validnextoutputs=" -o "+listOptions['transaction_to']+":"+str(to_fee)

#if there's any leftover change above dust send it back to yourself
if change >= output_minimum: 
    validnextoutputs+=" -o "+listOptions['transaction_from']+":"+str(change)

#create a temp file for the unsigned raw tx and the signed tx data for sx
#format: sender_address.recpt_address.secs_since_1970.random_hex
unsigned_raw_tx_file = DATA+listOptions['transaction_from']+'.'+listOptions['transaction_to']+'.'+commands.getoutput('date +%s')+'.'+hex(random.randint(0,255))[2:].rjust(2,"0")
signed_raw_tx_file = unsigned_raw_tx_file+'.signed'

#store the unsigned tx data in the file
commands.getoutput('sx mktx '+unsigned_raw_tx_file+' '+validnextinputs+' '+validnextoutputs)

#verify that transaction is valid
pht = commands.getoutput('cat '+unsigned_raw_tx_file+' | sx showtx -j')

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
    exit()

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
