#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# this script is called by cron with uid drucker every 5 minutes
# (see crontab of user "drucker")

import sys
import MySQLdb
from datetime import date, timedelta
import locale
import subprocess
import os

outputformat = "png"
outputwidth = 490
outputheight = 350
outputfile = "/var/www/intranet/printerstats/druckergraph"
gnuplot_binary = "/usr/bin/gnuplot"
mysql_config = "/usr/lib/drucker/my.cnf"
sql = "SELECT sum(pages) FROM Drucken WHERE state = 'DONE' AND " \
                "date >= %s AND date < %s"

#mode:
#0: weekly view
#1: monthly view

xtitle = ("Gedruckte Seiten pro Tag", "Gedruckte Seiten pro Monat")
ytitle = ("", "")
time_format_sql = "%Y-%m-%d"
time_format_label = ("%a, %d. %b", "%b %Y")
plotrange = (15, 15)
output_append = ("tag", "monat")

def first_date(mode, now):
    if mode == 0:
        return now-timedelta(days=plotrange[mode]-1)
    elif mode == 1:
        month = now.month-plotrange[mode]+1
        year = now.year
        while month <= 0:
            year -= 1
            month += 12
        return date(year, month, 1)
    else:
        print "Error: Unknown Mode: %d" % (mode,)
        exit(1)

def next_date(workdate, mode):
    if mode == 0:
        workdate += timedelta(days=1)
    elif mode == 1:
        if workdate.month < 12:
            workdate = workdate.replace(month=workdate.month+1)
        else:
            workdate = workdate.replace(month=1, year=workdate.year+1)
    else:
        print "Error: Unknown Mode: %d" % (mode,)
        exit(1)
    return workdate

def gen_graph(cursor, mode):
    # Get actual date
    now = date.today()
    weekday = now.weekday()
    process_date = first_date(mode, now)
    pages = list()
    labels = list()
    end = process_date.strftime(time_format_sql)
    for i in range(plotrange[mode]):
        start = end
        labels.append(process_date.strftime(time_format_label[mode]))
        process_date = next_date(process_date, mode)
        end = process_date.strftime(time_format_sql)
        # get sum for range
        cursor.execute(sql, (start, end))
        r = cursor.fetchall()
        if r[0][0]:
            pages.append(r[0][0])
        else:
            pages.append(0)
    avg = float(sum(pages))/len(pages)
    of = outputfile + "_" + output_append[mode] + "." + outputformat
    plot_generation = \
            "set xlabel \"" + xtitle[mode] + "\"\n" \
            "set ylabel \"" + ytitle[mode] + "\"\n" \
            "set encoding utf8\n" \
            "set terminal " + outputformat + " size " + str(outputwidth) + \
            "," + str(outputheight) + "\n" \
            "set output '" + of + ".tmp'\n" \
            "set style fill solid 1.00 border -1\n" \
            "set style data histogram\n" \
            "set style histogram cluster gap 1\n" \
            "set xtics nomirror rotate by -45\n" \
            "set xrange [-0.5:" + str(plotrange[mode] - 0.5) + "]\n" \
            "set yrange [0:]\n" \
            "f(x) = " + str(avg) + "\n" \
            "plot f(x) title 'Durchschnitt' with lines lw 2, \\\n" \
            "'-' using 2:xtic(1) notitle linecolor rgb \"#008800\"\n" \
            + '\n'.join(map(lambda x,y: '"%s" %d' %(x, y), labels, pages)) \
            + '\ne'
    p = subprocess.Popen([gnuplot_binary], shell=False,
                         stdin=subprocess.PIPE)
    p.communicate(input=plot_generation)
    # rename file to avoid inavailability of graphic file
    os.rename(of + ".tmp", of)

def main():
    # german output of weekdays / months :)
    locale.setlocale(locale.LC_ALL, ('de_de', 'utf8'))
    #mysql init
    conn = MySQLdb.connect(host="localhost", db="VereinII",
                           read_default_file=mysql_config,
                          charset = "utf8", use_unicode = False)
    cursor = conn.cursor()
    gen_graph(cursor, 0)
    gen_graph(cursor, 1)
    #mysql close
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()
