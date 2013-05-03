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
from hashlib import md5
import collections
import logging
import os
import quopri
import socket
import sys
import traceback

import mechanize
import urllib
import urlparse
import re
import HTMLParser

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
    return "+OK %i %i" % (len(scrapper.coda), scrapper.size(0))
    #return "-ERR No such message"

def handleList(data, scrapper):
    K=100
    ret = "+OK %i messages (%i octets)\r\n" % (len(scrapper.coda), K*len(scrapper.coda))
    for i in xrange(1, len(scrapper.coda)+1 ):
        ret = ret + "%i %i\r\n" % (i, K)
    ret = ret + "."
    return ret

def handleTop(data, scrapper):
    cmd, num, lines = data.split()
    num = int(num)
    return "+OK top of message follows\r\n%s\r\n." % scrapper.top(num-1)

def handleRetr(data, scrapper):
    cmd, num = data.split()
    num = int(num)
    log.info("message sent")
    msg =  scrapper.top(num-1)+scrapper.body(num-1)
    return "+OK %i octets\r\n%s\r\n." %(len (msg), msg )

def handleDele(data, scrapper):
    cmd, num = data.split()
    num = int(num)
    scrapper.delete(num-1)
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
    cache = collections.defaultdict(dict)

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
        self.cache = collections.defaultdict(dict)
        self.baseurl = "http://www.libero.it/"
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)
        self.br.addheaders = [('User-agent', 'Mozilla/5.0 (Linux; U; Android 4.1.1; he-il; Nexus 7 Build/JRO03D) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30')]

        response = self.br.open(self.baseurl)
        self.log(response)

        response = self.br.follow_link(text="MAIL", nr=0)
        self.log(response)

        response.info()['content-type'] = ' text/html; charset=utf-8'
        self.br.select_form(nr=0)
        self.br['LOGINID'] = self.username
        self.br['PASSWORD'] = _pass
        response = self.br.submit()
        self.html = response.read()
        self.log(response, self.html)
                
        next_url = re.findall(r'id="main"\s*src="([^"]*)"', self.html, re.I)
        print next_url
        if next_url:
            self.get(next_url[0])
            self.baseurl = next_url[0] 
        else:
            return 0      

        self.br.select_form(nr=0)
        response = self.br.submit()
        self.html = response.read()
        self.log(response, self.html)
        
        self.token_hash = ''.join ( re.findall(r'tokenHash\s*:\s*"([^"]*)"', self.html, re.I) )

        next_url_2 = re.findall(r'mailFrameUrl:"/cp/ps/Mail/MailFrame\?([^"]*)"', self.html, re.I)
        if next_url_2:
            url = "/cp/ps/Mail/commands/SyncFolder?%s#" % next_url_2[0]
            self.get( next_url[0], url )
            self.params = next_url_2[0]
        else:
            return 0      
                
        self.coda = self.messaggi()
        #return not ("Libero ID o password errata." in self.html or "Libero ID non valido." in self.html)
        return 1

    def size(self,n):
        ret = len( self.top(n) ) + len( self.body(n) )
        return ret

    def follow_src(self, html):
        ret = []
        for url in re.findall ( r'src="([^"]*")' , html, re.I ):
            ret.append( self.get( url ) )
        return ret

    def filter_message(self, html):
        mark = '<div class="onlyMessage" id="onlyMessage">'
        ret = ''
        if mark in html:
            start = html.find(mark)
            ptr = start+len(mark)
            depth = 1
            len_html = len(html)
            while depth and ptr<len_html:
                if html[ptr:ptr+4].lower() == '<div': #@todo replace with regex
                    depth += 1
                elif html[ptr:ptr+5].lower() == '</div': #@todo replace with regex
                    depth -= 1
                ptr += 1;
            if depth == 0:
                ret = html[start+len(mark) : ptr-1]
        return ret

    def messaggi(self):
        ret = []
        data = re.findall(r'id="([a-z0-9]*)" uid="(\d+)" i="(\d+)" from="([^"]*)"', self.html, re.I)
        if self.DEBUG and data: data = data[:2]
        ret = dict ( [ ( int(x[2]), x ) for x in data ] )
        return ret

    def boundary(self, x):
        ret = re.findall(r'boundary\s*=\s*["]?(.*?)[";\r\n]', x, re.I)
        if ret:
            return ret[0]
        else:
            return None

    def delete(self,n):
        #"http://posta18.posta.libero.it/cp/ps/Mail/commands/DeleteMessage?d=libero.it&u=gambuzzi&t=d122d4d30d539567&lsrt=25805"
        #POST selection=3ae36564bd31ad576fa316a61d7c8030
        pid, uid, i, _from = self.coda[n]
        url = "/cp/ps/Mail/commands/DeleteMessage?"
        full_url = url + self.params
        dizio = {'selection' : pid}
        self.br.open( urlparse.urljoin( self.baseurl, full_url ) , urllib.urlencode(dizio) )

    def top(self, n):
        if n not in self.cache['top']:
            pid, uid, i, _from = self.coda[n]

            url = "/cp/ps/Mail/commands/LoadMessage?"
            full_url = url + self.params +'&'+ urllib.urlencode( {
              'pid':pid,
              'uid':uid,
              'an':'DefaultMailAccount',
              'fp':'inbox',
              'sh':'true',
            } )
            _top = [self.htmlparser.unescape( x.strip().strip('<pre>').strip('</pre>') ) for x in self.get ( self.baseurl, full_url).splitlines() if x.strip().strip('<pre>').strip('</pre>')]
            _top = '\r\n'.join(_top[:-1])

            s = re.compile(r';\s*boundary', re.I)
            _top = s.sub('; boundary', _top)

            s = re.compile(r';\s*charset', re.I)
            _top = s.sub('; charset', _top)

            s = re.compile(r'\bquoted-printabl\b', re.I)
            _top = s.sub('quoted-printable', _top)

            s = re.compile(r'Content-Transfer-Encoding: .*', re.I)
            _top = s.sub('Content-Transfer-Encoding: quoted-printable', _top)

            b = self.boundary(_top)
            if b:
                _top = _top.replace(b, md5( os.urandom(10) ).hexdigest() )

            self.cache['top'][n] = _top

        return self.cache['top'][n]

    def body(self, n):
        if n not in self.cache['body']:
            pid, uid, i, _from = self.coda[n]

            url = "/cp/ps/Mail/commands/LoadMessage?"
            full_url = url + self.params +'&'+ urllib.urlencode( {
              'pid':pid,
              'uid':uid,
              'an':'DefaultMailAccount',
              'fp':'inbox',
            } )
            self.get ( self.baseurl, full_url)

            url = "/cp/MailMessageBody.jsp?"
            full_url = url + urllib.urlencode( {
              'pid' : pid,
              'th'  : self.token_hash,
            } )
            _body = self.filter_message( self.get ( self.baseurl, full_url) )
            _top = self.top(n)
            boundary = self.boundary(_top)
            if boundary:
                _body = "\r\n\r\n\r\n--" + boundary + "\r\nContent-Type: text/html; charset=UTF-8\r\n"+\
                        "Content-Transfer-Encoding: quoted-printable\r\n\r\n" + quopri.encodestring(_body.strip(' \r\n')) + \
                        "\r\n\r\n--" + boundary + "--\r\n"
            else:
                _body = "\r\n\r\n" +  quopri.encodestring( _body.strip(' \r\n') ) + "\r\n\r\n"

            self.cache['body'][n] = _body
        return self.cache['body'][n]

    def get(self, url, url_to_join = None ):
        if url_to_join:
            url = urlparse.urljoin( url, url_to_join )
            if self.DEBUG: print url
        response = self.br.open(url)
        self.html = response.read()
        self.log(response, self.html)
        return self.html

    def __init__(self):
        self.htmlparser = HTMLParser.HTMLParser()

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

            