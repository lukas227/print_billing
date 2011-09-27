#!/usr/bin/env python
# -*- coding: UTF-8 -*-

#  prehook script
# the following data must be available via environment:
# TEACLIENTHOST TEADATAFILE TEAJOBID TEATITLE
# expects the following two positional arguments:
# OPERATION [must be PRINT or CALC]
# PRINTER [for logging purposes]

# depending on OPERATION, we do only pricecalc or real print

import os
import sys
import traceback
sys.path.append('/usr/lib/drucker')
import druckerlib
import re
import subprocess

#configurable stuff
warnlimit = 500
pkpgcounter_bin = '/usr/bin/pkpgcounter'
#end configurable stuff

#regexes used
is_adobe_ps = re.compile(r'^%!PS-Adobe-3.0')
is_duplex = re.compile(r'^\s*<</Duplex true /Tumble (true|false)\s*>>')
is_blackwhite = re.compile(r'^\s*<</ProcessColorModel /DeviceGray>>')
pkpgcounter_color_regex = re.compile(r'^C :\s*(\d*\.\d*)%\s*' \
                                     r'M :\s*(\d*\.\d*)%\s*' \
                                     r'Y :\s*(\d*\.\d*)%\s*' \
                                     r'K :\s*(\d*\.\d*)%\s*$')
pkpgcounter_blackwhite_regex = re.compile(r'^B :\s*(\d*\.\d*)%\s*$')
smprnt_title_regex = re.compile(r'^smbprn.\d* (.*)$')
#end regexes used

def print_pricecalc(dl, ipaddr, datafile, jobid, printstate,
                    jobtitle, printername, baseIP, room, uid):
    dl.setlogstring("pricecalc-" + jobid)

    infile = open(datafile, "r")

    p = subprocess.Popen([pkpgcounter_bin, datafile],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = p.communicate()
    stdout = out[0].rstrip()
    try:
        pages = int(stdout)
    except (TypeError, ValueError):
        dl.logit("Pages count from pkpgcounter (%s) is " \
                 "not an integer" % (out,), 1)
    dl.logit("Number of pages is " + str(pages), 0)
    stderr = out[1].rstrip()
    if stderr != '':
        dl.logit("Stderr pkpgcounter: %s" % (stderr,), 0)

    # Get Infos from Inputfile
    adobe_ps = False
    duplex = False
    blackwhite = False
    for line in infile:
        if (not adobe_ps) and is_adobe_ps.match(line):
            adobe_ps = True
        elif (not duplex) and is_duplex.match(line):
            duplex = True
        elif (not blackwhite) and is_blackwhite.match(line):
            blackwhite = True

    # process infos
    if not adobe_ps:
        dl.logit("Wrong fileformat (not Postscript), maybe wrong driver?", 1)

    #dl.logit("Datafile: %s" % (datafile,), 0)
    sum_cyan = sum_magenta = sum_yellow = sum_black = 0.0
    linecount = 0
    if blackwhite:
        bw_color = "black/white"
        dl.logit("Black toner coverage:", 0)
        p = subprocess.Popen([pkpgcounter_bin, '--colorspace', 'bw',
                              '-r144', datafile],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.communicate()
        stdout = out[0].rstrip()
        for line in stdout.split('\n'):
            if line[0] == '%':
                continue
            m = pkpgcounter_blackwhite_regex.match(line)
            if m:
                dl.logit(m.group(1), 0)
                sum_black += float(m.group(1))
                linecount += 1
            else:
                dl.logit("Unknown Line (pkpgcounter-output bw): " + line, 1)
        stderr = out[1].rstrip()
        if stderr != '':
            dl.logit("Stderr pkpgcounter: %s" % (stderr,), 0)
    else:
        bw_color = "color"
        dl.logit("Toner coverage (cyan::magenta::yellow::black):", 0)
        p = subprocess.Popen([pkpgcounter_bin, '--colorspace', 'cmyk',
                              '-r144', datafile],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.communicate()
        stdout = out[0].rstrip()
        for line in stdout.split('\n'):
            if line[0] == '%':
                continue
            m = pkpgcounter_color_regex.match(line)
            if m:
                dl.logit('::'.join([m.group(i) for i in range(1,5)]), 0)
                sum_cyan += float(m.group(1))
                sum_magenta += float(m.group(2))
                sum_yellow += float(m.group(3))
                sum_black += float(m.group(4))
                linecount += 1
            else:
                dl.logit("Unknown Line (pkpgcounter-output color): " + line, 1)
        stderr = out[1].rstrip()
        if stderr != '':
            dl.logit("Stderr pkpgcounter: %s" % (stderr,), 0)

    if pages != linecount:
        dl.logit("Number of pages doesn't match the number of lines for " \
                 "cost calculation; using linecount", 0)
        pages = linecount

    # price calculation for black toner usage:
    # our cost for black toner is about 140€ for 10500 pages based on 
    # 5% toner usage; this means 1.33¢ = 13.3 millicent for a 5% covered page.
    # We will use 15 millicent instead, to earn some extra $$$ :)
    black_toner_pages = sum_black/5
    price_black = int(round(black_toner_pages * 15))

    # price calculation for color toner usage:
    # our cost for color toner (same for all colors) is about 190€ for 7000
    # pages based on 5% toner usage; this means 2.71¢ = 27.1 millicent
    # for a 5% covered page. We will use 40 millicent instead, since I have
    # noticed, that the printer uses more toner than the pkpgcounter assumes
    color_toner_pages = (sum_cyan+sum_magenta+sum_yellow)/5
    price_color = int(round(color_toner_pages*40))

    # an additional 2 millicent per page for FUSER and TONER_COLLECTOR costs
    price_printer = price_black + price_color + pages*2

    # charge 8 millicent per page
    if duplex:
        # round up on odd pagenumber
        price_paper = (pages+1)/2*8
        duplex_simplex = "duplex"
    else:
        price_paper = pages*8
        duplex_simplex = "simplex"

    price = price_printer + price_paper

    if price <= 0:
        dl.logit("Price would be %d (impossible), aborting..." % (price,), 1)

    dl.logit("Price for %s %s job is %d millicents" % (duplex_simplex,
                                                       bw_color, price), 0)

    sql = "INSERT INTO Drucken (uid,jid,jname,used_cyan,used_magenta," \
            "used_yellow,used_black,price_printer,price_paper,price,pages," \
            "state) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    dl.mysql_query(sql, (uid,jobid,jobtitle,int(round(sum_cyan*1000)),
                         int(round(sum_magenta*1000)),
                         int(round(sum_yellow*1000)),int(round(sum_black*1000)),
                         price_printer,price_paper,price,pages,printstate))
    #data is in db, finished... 
    #since we might need the price, we will return it
    return price

def print_auth(dl, ipaddr, jobid, price, baseIP, room, limit, uid):
    dl.setlogstring("auth-" + jobid)

    #we already know the price ;)
    #price = dl.getPrice(jobid)
    balance = dl.getPrintBalance(uid)

    dl.logit("Balance for user is %d" % (balance,), 0)
    # Check if User has to pay the job
    cm = dl.getChargeMode(uid)
    if cm != 'private':
        sql = "UPDATE User SET next_print = 'private' WHERE uid = %s LIMIT 1"
        dl.mysql_query(sql, (uid,))
        sql = "UPDATE Drucken SET type=%s WHERE jid=%s ORDER BY " \
                "date DESC LIMIT 1"
        dl.mysql_query(sql, (cm,jobid))
        dl.logit("Print is for %s, user will not be charged" % (cm,), 0)
    else:
        # Check if User can afford job
        if (balance-price) < (limit+warnlimit) and (balance-price) >= limit:
            dl.logit("User %s is close to limit" % (uid,), 0)
        elif (balance-price) < limit:
            sql="UPDATE Drucken SET state='STOP' WHERE jid=%s " \
                    "ORDER BY date DESC LIMIT 1"
            dl.mysql_query(sql, (jobid,))
            dl.logit("User %s has reached the limit. Stopped Job!" % (uid,), 1)
    dl.logit("Authorizing printing Job (price: %s) for %s in Room %s " \
             "for addr %s" % (price, uid, room, ipaddr), 0)

def main():
    os.chdir("/tmp")
    ipaddr = os.environ['TEACLIENTHOST']
    datafile = os.environ['TEADATAFILE']
    jobid = os.environ['TEAJOBID']
    jobtitle = os.environ['TEATITLE']
    m = smprnt_title_regex.match(jobtitle)
    if m:
        jobtitle = m.group(1)
    operation = sys.argv[1]
    printername = sys.argv[2]
    
    dl = druckerlib.DruckerLib("init-" + jobid)
    try:
        dl.logit("-- PREHOOK STARTING --", 0)
        baseIP = dl.getBaseIP(ipaddr, 30)
        room = dl.getRoom(baseIP)
        uid = dl.getUserID(room)
        limit = dl.getPrintLimit(uid)
        (nick, firstname, lastname) = dl.getUserinfos(uid)
        dl.logit("Job for %s %s (%s), Uid: %d, Room: %d, " \
                 "Printlimit: %d" % (firstname, lastname,nick, uid, room, limit), 0)
	dl.logit("From IP: %s, Title: %s, Type: %s" % (ipaddr,jobtitle, operation), 0)

        if operation == "PRINT":
            price = print_pricecalc(dl, ipaddr, datafile, jobid, "INIT", jobtitle,
                                    printername, baseIP, room, uid)
            print_auth(dl, ipaddr, jobid, price, baseIP, room, limit, uid)
        elif operation == "CALC":
            print_pricecalc(dl, ipaddr, datafile, jobid, "CALC", jobtitle,
                            printername, baseIP, room, uid)
        else:
            dl.logit("Unknown value for $OPERATION: " + operation, 1)
        dl.logit("-- PREHOOK FINISHED --", 0)
    except Exception as e:
        f = open('/var/log/drucker_error.log', 'a')
        for l in traceback.format_exception(*sys.exc_info()):
            f.write(l)
        f.close()
        dl.logit("Terminated with error, see /var/log/drucker_error.log", 1)
    del dl

if __name__ == "__main__":
    main()
