# -*- coding: UTF-8 -*-

import sys
import re
import MySQLdb
from datetime import datetime

verbose = False
logfile = "/var/log/drucker.log"
mysql_config = "/usr/lib/drucker/my.cnf"

class DruckerLib:
    #constructor
    def __init__(self, logstring):
        self.logstring = logstring
        self.out = open(logfile, 'a')
        try:
            self.conn = MySQLdb.connect(host="localhost", db="VereinII",
                                       read_default_file=mysql_config,
                                       charset = "utf8", use_unicode = False)
            self.cursor = self.conn.cursor()
        except MySQLdb.Error, e:
            self.logit("%d: %s" % (e.args[0], e.args[1]), 1)

    #destructor
    def __del__(self):
        try:
            self.out.close()
            self.cursor.close()
            self.conn.close()
        except:
            pass

    def setlogstring(self, logstring):
        self.logstring = logstring

    #central log function
    def logit(self, msg, status):
        if status != 0:
            self.out.write("%s %s: Error: %s\n" \
                           % (datetime.now().strftime("%b %e %T"),
                              self.logstring, msg))
            exit(-1)
        self.out.write("%s %s: %s\n" % (datetime.now().strftime("%b %e %T"), 
                                        self.logstring, msg))

    #central mysql query function
    def mysql_query(self, sql, params):
        if verbose:
            self.logit("SQL Query: " + sql % params, 0)
        try:
            self.cursor.execute(sql, params)
            r = self.cursor.fetchall()
        except MySQLdb.Error, e:
            self.logit("%d: %s" % (e.args[0], e.args[1]), 1)
        return r

    #get first address of the range ip/netmask
    def getBaseIP(self, ip, netmask):
        split_ip = re.compile(r"^((?:[0-9]+\.){3})([0-9]+)$")
        m = split_ip.match(ip)
        if m:
            shift = 32-netmask
            ld = (int(m.group(2)) >> shift) << shift
            return m.group(1) + str(ld)
        else:
            self.logit("Not a valid IP: %s" % ip, 1)

    #get room from baseip via mysql
    def getRoom(self, baseip):
        sql ="SELECT Zimmer FROM Zimmer WHERE IP=%s OR wlanIP=%s LIMIT 1"
        r = self.mysql_query(sql, (baseip, baseip))
        if len(r) == 0:
            self.logit("Zimmer for %s not found" % (baseip,), 1)
        room = r[0][0]
        if verbose:
            self.logit("Zimmer is %s" % (room,), 0)
        return room

    #get uid from roomnumber
    def getUserID(self, room):
        sql = "SELECT uid FROM Wohnen WHERE auszug IS NULL " \
                "AND zimmer=%s LIMIT 1"
        r = self.mysql_query(sql, (room,))
        if len(r) == 0:
            self.logit("Could not get UID for Room %s" % (room,), 1)
        uid = r[0][0]
        if verbose:
            self.logit("UID is " + str(uid), 0)
        return uid

    def getPrice(self, jobid):
        sql="SELECT price FROM Drucken WHERE jid=%s AND "\
                "state='INIT' ORDER BY date DESC LIMIT 1"
        # we only take init here, so we abort in case we already set the job to
        # stop (happens if user uses a wrong printer driver)
        r = self.mysql_query(sql, (jobid,))
        if len(r) == 0:
            self.logit("Jobid %s not found in Database" % (jobid,), 1)
        return r[0][0]

    def getPrintLimit(self, uid):
        sql = "SELECT druckerlimit drl FROM User WHERE uid=%s LIMIT 1" 
        r = self.mysql_query(sql, (uid,))
        if len(r) == 0:
            self.logit("Could not get druckerlimit for uid %s" % (uid,), 1)
        pl = r[0][0]
        if verbose:
            self.logit("Printinglimit is " + str(pl), 0)
        return pl

    def getUserinfos(self, uid):
        sql = "SELECT nick, vorname, name FROM User WHERE uid=%s LIMIT 1" 
        r = self.mysql_query(sql, (uid,))
        if len(r) == 0:
            self.logit("Could not get userinfos for uid %s" % (uid,), 1)
        if verbose:
            self.logit("Username: %s, Firstname: %s, Lastname: %s " % r[0], 0)
        return r[0]

    def getPrintBalance(self, uid):
        sql = "SELECT saldo FROM User WHERE uid=%s LIMIT 1"
        r = self.mysql_query(sql, (uid,))
        if len(r) == 0:
            self.logit("Could not get Printerbalance for uid %s" % (uid,), 1)
        balance = r[0][0]
        if verbose:
            self.logit("Balance is " + str(balance), 0)
        return balance

    def getChargeMode(self, uid):
        sql = "SELECT next_print FROM User WHERE uid=%s LIMIT 1"
        r = self.mysql_query(sql, (uid,))
        if len(r) == 0:
            self.logit("Could not get next_print for uid %s" % (uid,), 1)
        charge_mode = r[0][0]
        if verbose:
            self.logit("Balance is " + str(balance), 0)
        return charge_mode

    def getChargeModeJid(self, jid):
        sql = "SELECT type FROM Drucken WHERE jid=%s " \
                "ORDER BY date DESC LIMIT 1"
        r = self.mysql_query(sql, (jid,))
        if len(r) == 0:
            self.logit("Could not get type for jid %s" % (jid,), 1)
        charge_mode = r[0][0]
        if verbose:
            self.logit("Balance is " + str(balance), 0)
        return charge_mode

    def abortJob(self, jid):
        sql="UPDATE Drucken SET state='STOP' WHERE jid=%s " \
                "ORDER BY date DESC LIMIT 1"
        self.mysql_query(sql, (jid,))
