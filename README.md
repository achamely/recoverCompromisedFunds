recoverCompromisedFunds
=======================

scripts to recover msc funds from a compromised address

Depends on: sx, python


fill in btc_example.json
cat btc_example.json | python makeBTCsend.py
  <creates tx #1, BTC funding tx>

fill in msc_example.json (you will need output of previous command)
cat msc_example.json | python createSpecial.py
  <Creates tx #2, MSC moving tx>

the two signed tx's are in the <local directory>/data
Broadcast the signed files ( tx #1, tx #2)  to obelisk and blockchain several times (recommend a quick loop) to make sure they are received.
