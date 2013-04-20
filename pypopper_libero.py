#!/usr/bin/env python
# -*- coding: UTF-8 -*-
# 
# (c) Roberto Gambuzzi
# Creato:          21/04/2013 00:00:11
# Ultima Modifica: 21/04/2013 00:00:44
# 
# v 0.0.1.0
# 
# file: C:\Dropbox\rgambuzzi(at)webgriffe.com\coding dojo\pypopper_libero\pypopper_libero.py
# auth: Roberto Gambuzzi <gambuzzi@gmail.com>
# desc: 
# 
# $Id: pypopper_libero.py 21/04/2013 00:00:44 Roberto $
# --------------
## {{{ http://code.activestate.com/recipes/534131/ (r1)
"""pypopper: a file-based pop3 server

Useage:
    python pypopper.py <port> <path_to_message_file>
"""
import logging
import os
import socket
import sys
import traceback

import mechanize
import urlparse
import re

logging.basicConfig(format="%(name)s %(levelname)s - %(message)s")
log = logging.getLogger("pypopper")
log.setLevel(logging.INFO)

class ChatterboxConnection(object):
    END = "\r\n"
    def __init__(self, conn):
        self.conn = conn
    def __getattr__(self, name):
        return getattr(self.conn, name)
    def sendall(self, data, END=END):
        if len(data) < 50:
            log.debug("send: %r", data)
        else:
            log.debug("send: %r...", data[:50])
        data += END
        self.conn.sendall(data)
    def recvall(self, END=END):
        data = []
        while True:
            chunk = self.conn.recv(4096)
            if END in chunk:
                data.append(chunk[:chunk.index(END)])
                break
            data.append(chunk)
            if len(data) > 1:
                pair = data[-2] + data[-1]
                if END in pair:
                    data[-2] = pair[:pair.index(END)]
                    data.pop()
                    break
        log.debug("recv: %r", "".join(data))
        return "".join(data)


class Message(object):
    def __init__(self, filename):
        msg = open(filename, "r")
        try:
            self.data = data = msg.read()
            self.size = len(data)
            self.top, bot = data.split("\r\n\r\n", 1)
            self.bot = bot.split("\r\n")
        finally:
            msg.close()


def handleUser(data, scrapper):
    scrapper.username = data.split(' ',1)[1]
    return "+OK user accepted"

def handlePass(data, scrapper):
    if hasattr(scrapper, 'username') and scrapper.login(data.split(' ',1)[1]):
        return "+OK pass accepted"
    else:
        return "-ERR Authentication failed."

def handleStat(data, scrapper):
    print data
    try:
        return "+OK 1 %i" % scrapper.size(1)
    except:
        return "-ERR No such message"

def handleList(data, scrapper):
    print data
    return "+OK 1 messages (%i octets)\r\n1 %i\r\n." % (scrapper.size(1), scrapper.size(1))

def handleTop(data, scrapper):
    print data
    cmd, num, lines = data.split()
    assert num == "1", "unknown message number: %s" % num
    lines = int(lines)
    text = msg.top + "\r\n\r\n" + "\r\n".join(msg.bot[:lines])
    return "+OK top of message follows\r\n%s\r\n." % text

def handleRetr(data, scrapper):
    print data
    log.info("message sent")
    msg =  scrapper.top_body(1)
    return "+OK %i octets\r\n%s\r\n." %(len (msg), msg )

def handleDele(data, scrapper):
    print data
    return "+OK message 1 deleted"

def handleNoop(data, scrapper):
    return "+OK"

def handleQuit(data, scrapper):
    return "+OK pypopper POP3 server signing off"

dispatch = dict(
    USER=handleUser,
    PASS=handlePass,
    STAT=handleStat,
    LIST=handleList,
    TOP=handleTop,
    RETR=handleRetr,
    DELE=handleDele,
    NOOP=handleNoop,
    QUIT=handleQuit,
)

def serve(host, port, scrapper):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, port))
    try:
        if host:
            hostname = host
        else:
            hostname = "localhost"
        log.info("pypopper POP3 serving '%s' on %s:%s", scrapper, hostname, port)
        while True:
            sock.listen(1)
            conn, addr = sock.accept()
            log.debug('Connected by %s', addr)
            try:
                conn = ChatterboxConnection(conn)
                conn.sendall("+OK pypopper file-based pop3 server ready")
                while True:
                    data = conn.recvall()
                    print "*"*40
                    print data
                    print "*"*40
                    command = data.split(None, 1)[0].upper()
                    try:
                        cmd = dispatch[command]
                    except KeyError:
                        conn.sendall("-ERR unknown command")
                    else:
                        conn.sendall(cmd(data, scrapper))
                        if cmd is handleQuit:
                            break
            finally:
                conn.close()
                msg = None
    except (SystemExit, KeyboardInterrupt):
        log.info("pypopper stopped")
    except Exception, ex:
        log.critical("fatal error", exc_info=ex)
    finally:
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()

class Libero(object):
    DEBUG = 1
    br=None
    progressivo = 0

    def strip_tags( self, html , r = ''):
        return re.sub(r'<[^>]*?>', r, html)

    def log(self, response, html =  None):
        if self.DEBUG:
            print response.info()
            if not html:
                html = response.read()
            open('log/out_%04i.html' % self.progressivo,'w').write(html)
            self.progressivo += 1

    def login(self, _pass):
        self.baseurl = "http://m.libero.it/"
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)
        self.br.addheaders = [('User-agent', 'Mozilla/5.0 (Linux; U; Android 4.1.1; he-il; Nexus 7 Build/JRO03D) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30')]

        response = self.br.open(self.baseurl)
        self.log(response)
        response = self.br.follow_link(text="Mail", nr=0)
        self.log(response)
        response.info()['content-type'] = ' text/html; charset=utf-8'

        self.br.select_form(nr=0)
        self.br['LOGINID'] = self.username
        self.br['PASSWORD'] = _pass
        response = self.br.submit()

        self.html = response.read()
        self.log(response,self.html)
        if self.DEBUG:
            self.coda = self.messaggi()
        else:
            self.coda = self.messaggi_non_letti()
        return not ("Libero ID o password errata." in self.html or "Libero ID non valido." in self.html)

    def top_body(self,n):
        n-=1
        url = self.coda[n][0]
        self.html = self.get (self.baseurl, url)


    def size(self,n):
        n-=1
        ret = self.coda[n][1].split()
        if ret[1].upper() == 'KB':
            ret = float(ret[0]) * 1024
        elif ret[1].upper() == 'MB':
            ret = float(ret[0]) * 1024 * 1024
        else:
            ret = float(ret[0])
        return ret

    def messaggi(self):
        ret = re.findall(r'href="(/m/wmm/read/INBOX/\d+/\d+)".*?(\d+\.\d+ .B)</span>', self.html, re.I)
        return ret

    def messaggi_non_letti(self):
        ret = re.findall(r'href="(/m/wmm/read/INBOX/\d+/\d+)".*?row_mail_element"><b>.*?(\d+\.\d+ .B)</span>', self.html, re.I)
        return ret

    def get(self, url, url_to_join = None ):
        if url_to_join:
            url = urlparse.urljoin( url, url_to_join )
        response = self.br.open(url)
        self.html = response.read()
        self.log(response, self.html)
        return self.html

    def __init__(self):
        pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "USAGE: [<host>:]<port>"
    else:
        _, port = sys.argv
        if ":" in port:
            host = port[:port.index(":")]
            port = port[port.index(":") + 1:]
        else:
            host = ""
        try:
            port = int(port)
        except Exception:
            print "Unknown port:", port
        else:
            serve(host, port, Libero())
