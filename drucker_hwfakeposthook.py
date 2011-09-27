#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# hardware posthook for the printing job
# check if printer has printed the correct number of pages
# validate job in the database! (or stop it)
# arguments for this program are $TEASTATUS, $TEAJOBID and $TEADATAFILE

import os
import sys
sys.path.append('/usr/lib/drucker')
import druckerlib

def main():
    ts = os.environ['TEASTATUS']
    jid = os.environ['TEAJOBID']
    dl = druckerlib.DruckerLib("posthook-" + jid)

    if ts != '0':
        dl.abortJob(jid)
        dl.logit("Cups Backand failed with status " + ts, 1)
    sql="SELECT price,uid FROM Drucken WHERE jid=%s " \
            "ORDER BY date DESC LIMIT 1"
    r = dl.mysql_query(sql, (jid,))
    if len(r) == 0:
        dl.abortJob(jid)
        dl.logit("Could not get data for jid " + jid, 1)
    price = r[0][0]
    uid = r[0][1]
    sql = "UPDATE Drucken SET state='DONE' WHERE jid=%s "\
            "ORDER BY date DESC LIMIT 1"
    dl.mysql_query(sql, (jid,))
    if dl.getChargeModeJid(jid) == 'private':
        sql = "UPDATE User SET saldo=saldo-%s WHERE uid=%s LIMIT 1"
        dl.mysql_query(sql, (price, uid))
    dl.logit("Posthook sucessfully completed", 0)

if __name__ == "__main__":
    main()
