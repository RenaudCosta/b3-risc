#!/usr/bin/env python2
# -*- coding: utf-8 -*-


# TODO: - add !status/!st command [OK]
#       - fix update_hist() [OK]
#       - add !players <serverName> command [OK]
#       - minor bug fixed [OK]
#       - add colors [OK]
#       - fix colors not working on non-console client [OK]
#       - remove ^1 etc from map names [OK]
#       - add aliases for args [OK]
#       - add !base64 / !sha1 / !md5 [OK]
#       - change lastposts to lastthreads / lt [OK]
#       - add bold colors [OK]
#       - add thread author [OK]
#       - v1.1
#--------
#       - use UDP instead of qstat stuff [OK]
#       - add !search <player> [OK]
#       - add !disasm [OK]
#       - add !hi <user> [OK]
#       - add <server> optional arg to !search && add limit of user output to !search [OK]
#       - make the distinction between players & bots [OK]
#       - fix server auth stuff [OK]
#       - v1.2
#--------
#       - add !ikick (in irc kick) [OK]
#       - !lt now returns a link to the last post in the thread [OK]
#       - write irc_is_admin(): returns auth + level from *nick* [OK]
#       - add required rights to help command [OK]
#       - add !ilt / !ileveltest command [OK]
#       - updated irc_is_admin [OK]
#       - fixed time response in TIME ctcp [OK]
#       - fixed unicode char causing crash [OK]
#       - improved debug info [OK]
#       - irc_is_on_channel() [OK] XXX: NEED FIX (too slow)
#       - irc_is_authed() [OK] XXX: NEED FIX (too slow)
#       - set cmd output in pm [OK]
#       - add support for pm cmds [OK]
#       - add support for @ prefixed cmd's [OK]
#       - add support for in-game calladmin cmd [OK]
#       - removed disasm [OK]
#       - add threading support for game events [OK]
#-------- v1.3
#       - add commands to set/get Cvars
#       - change colors in game events ? (kick,pb etc) 


__author__  = 'Pr3acher'
__version__ = '1.3'


import socket
import threading
import time
import sys
import os
from bs4 import BeautifulSoup
import urllib2
import ConfigParser
import re
import base64
import hashlib
import MySQLdb as mysql


HELP = """Available commands: \
!help : Displays this help message. Can also be use like !help <command>,\
!ishowadmins,\
!hello,\
!disconnect,\
!lastthreads,\
!status,\
!players,\
!base64,\
!sha1,\
!md5,\
!search,\
!kick,\
!iputgroup\
!ileveltest. The commands prefixed by 'i' simply indicate that they're related to IRC management. Your can report any bug at pr3acher777h@gmail.com"""
IS_GLOBAL_MSG = 0 # set if the command starts with '@' instead of '!'
INIPATH = "risc.ini"

# irc color codes
COLOR={'boldwhite':'\x02\x030','green':'\x033','red':'\x035','magenta':'\x036','boldmagenta':'\x02\x036','blue':'\x032','boldred':'\x02\x034','boldblue':'\x02\x032','boldgreen':'\x02\x033','rewind':'\x0f'}


##########################################################################################################
#                                                                                                        #
#                                                                                                        # 
#                                       START HERE                                                       #
#                                                                                                        #
#                                                                                                        #
##########################################################################################################


class Debug:
    def __init__(self,use__stdout__): # use__stdout__ ? use screen output : use log file
        if not use__stdout__:
            sys.stdout = open("risc_"+str(int(time.time()))+'.log',"w+",0) # open file unbuffered
        return None


    def info(self,info_msg):
        t = time.localtime()
        print '%d/%d %d:%d:%d INFO %s' %(t[1],t[2],t[3],t[4],t[5],info_msg)
        return None


    def debug(self,debug_msg):
        t = time.localtime()
        print '%d/%d %d:%d:%d DEBUG %s' %(t[1],t[2],t[3],t[4],t[5],debug_msg)
        return None


    def warning(self,warning_msg):
        t = time.localtime()
        print '%d/%d %d:%d:%d WARNING %s' %(t[1],t[2],t[3],t[4],t[5],warning_msg)
        return None


    def error(self,error_msg):
        t = time.localtime()
        print '%d/%d %d:%d:%d ERROR %s' %(t[1],t[2],t[3],t[4],t[5],error_msg)
        return None


    def critical(self,critical_msg):
        t = time.localtime()
        print '%d/%d %d:%d:%d CRITICAL %s' %(t[1],t[2],t[3],t[4],t[5],critical_msg)
        return None

    
class Sv():
    """
    Gather info about a specific UrT 4.2 server
    """
    def __init__(self,ip,port,name=""):
        if re.match('([0-9]{1,3}\.){3}[0-9]{1,3}',ip) == None:  # Do we have a 'valid' IP ?
            print 'Sv.__init__: IP seems invalid - Returning 0'
            return 0
        self.ip = ip
        self.port = port
        self.name = name
        self.clientsPings = []
        try:
            self.sock = socket.socket(socket.AF_INET,socket.SOCK_DGRAM) # use UDP for UrT
            self.sock.connect((ip,port))
        except:
            if self.sock:
                self.sock.close()
            return 0
        if not self.getstatus():
            if self.sock:
                self.sock.close()
            return 0
        if not self.getinfo():
            if self.sock:
                self.sock.close()
            return 0
        self.check_vars()
        self.sock.close()
        return None


    def list_clean(self,l):
        retList = []
        for i in l:
            if i != '' and i !=' ':
                retList.append(i)
        return retList


    # returns the player list in the server, sets the ping list
    def get_clients_list(self,raw):
        cl = re.findall('".+',raw[len(raw)-1]) # find nicks, which are surrounded by "
        if not cl:
            return -1 # no players
        for i in range(len(cl)):
            cl[i] = re.sub('\^.','',cl[i])[1:][:-1]

        # retrieve pings in the same order of players
        pings = re.findall('\\n[0-9]{1,3}\s[0-9]{1,3}\s',raw[len(raw)-1])
        if len(pings) > 0:
            for i in range(len(pings)):
                pings[i] = pings[i].split(' ')[1]
            self.clientsPings=pings

        return cl


    # returns -1 if var isn't in the list
    def get_var(self,l,var):
        for i in range(len(l)):
            if l[i] == var:
                return l[i+1]
        return -1

    
    def check_vars(self):
        if self.allowVote == -1:
            self.allowVote = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.version == -1:
            self.version = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.gameType == -1:
            self.gameType = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.nextMap == -1:
            self.nextMap = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.clients == -1:
            self.clients = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.maxClients == -1:
            self.maxClients = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        if self.mapName == -1:
            self.mapName = COLOR['boldmagenta']+'Not set'+COLOR['rewind']
        return None


    def getstatus(self):
        try:
            self.sock.send(b'\xff'*4+b'getstatus')
            rawStatus = str(self.sock.recv(4096))
            listStatus = self.list_clean(rawStatus.split('\\'))
        except Exception, e:
            print 'Sv.getstatus: Exception: %s - Returning 0' % e
            return 0
        self.allowVote = self.get_var(listStatus,'g_allowvote')
        self.version = self.get_var(listStatus,'version')
        self.gameType = self.get_var(listStatus,'g_gametype')
        self.nextMap = self.get_var(listStatus,'g_NextMap')
        self.clientsList = self.get_clients_list(listStatus)
        return 1


    def getinfo(self):
        try:
            self.sock.send(b'\xff'*4+b'getinfo')
            rawInfo = str(self.sock.recv(2048))
            listInfo = self.list_clean(rawInfo.split('\\'))
        except Exception, e:
            print 'Sv.getinfo: Exception: %s - Returning 0' % e
            return 0
        self.clients = self.get_var(listInfo,'clients')
        self.authNotoriety = self.get_var(listInfo,'auth_notoriety')
        self.maxClients = self.get_var(listInfo,"sv_maxclients")
        self.mapName = self.get_var(listInfo,'mapname')
        return 1

    
class Risc():
    """
    Main class containing cmd_* functions
    """
    def __init__(self):
        try:
            self.debug = Debug(0)
            self.cfg = ConfigParser.ConfigParser()
            self.cfg.read(INIPATH)

            self.host = self.cfg.get('irc','host')
            self.port = int(self.cfg.get('irc','port'))
            self.channel = self.cfg.get("irc","channel")
            self.nick = self.cfg.get("irc","nick")
            self.forum = self.cfg.get("var","forum")
            self.refreshLastThreads = int(self.cfg.get("var","refreshlastthreads"))  # delay after which we query the website, not the cached info

            # use same db for both bot & plugin (b3 by default)
            # bot: table irc_admin; plugin: table <server_name> in <servers>
            self.db_host = self.cfg.get('db','host')
            self.db_user = self.cfg.get('db','user')
            self.db_passwd = self.cfg.get('db','passwd')
            self.db_name = self.cfg.get('db','name')

            # get the servers on which riscb3 is running
            self.sv_running = (self.cfg.get('var','svrunning').split(','))
        except:
            self.debug.critical("Risc.__init__: Exception caugth while loading config settings - Make sure there's no missing field")
            raise SystemExit

        # commands and aliases
        self.commands = {"!quit":["!quit","!leave","!disconnect","!die","!q"],\
                         "!help":["!h","!help"],\
                         "!lastthreads":["!lt","!lastthreads"],\
                         "!ishowadmins":["!isa","!ishowadmins"],\
                         "!hello":["!hi","!hello"],\
                         "!status":["!status","!st"],\
                         "!players": ["!players","!p"],\
                         "!base64" : ["!b64","!base64"],
                         "!sha1" :["!sha1"],\
                         "!md5" :["!md5"],\
                         "!search" :['!search','!s'],\
                         "!ikick": ["!ikick","!ik"],\
                         "!iputgroup" :["!iputgroup","!ipg"],\
                         "!ileveltest" :['!ileveltest','!ilt']}

        # commands that need some rights (temp)
        self.commandLevels = {"!quit": 80,\
                              "!ikick": 80,\
                              "!iputgroup": 100,\
                              "!ileveltest": 60}

        # valid argument for each commands
        self.args = {"!status": ["all","deathrun","jump","gunmoney","zombmoney","sr8","cubelowgrav"],\
                     "!players": ["deathrun","jump","gunmoney","zombmoney","sr8","cubelowgrav"],\
                     "!search": ["deathrun","jump","gunmoney","zombmoney","sr8","cubelowgrav"],\
                     "!iputgroup" : [60,80]} # available admin group: 60, 80

        # commands arguments aliases 
        self.argAliases = {'servers': {"deathrun": ["deathrun","dt","dr","death"],\
                                        "jump": ["jump","j","jmp"],\
                                        "gunmoney": ["gunmoney","gm","gun"],\
                                        "zombmoney": ["zombmoney","zm","zomb"],\
                                        "sr8" :["sr8","sr"],\
                                        "cubelowgrav" :['cubelowgrav','cube','clg']}}

        return None


    def start(self):
        """
        Launches the bot: connect, start event dispatcher, join
        """
        self.init_irc_admins()
        self.connect()
        self.debug.info('[+] Connected on '+self.host+' port '+str(self.port))
        self.set_evt_callbacks()  # not working yet...
        self.dispatcher() 
        return None


    def exit_process(self,msg="exit_process: Exiting"):
        self.debug.info(msg)
        time.sleep(0.3)
        sys.exit(0)
        return None


    def on_welcome(self):
        """
        This will be called when we join on the channel, ie after we successfully connected to the server
        """
        self._send("PRIVMSG Q@CServe.quakenet.org :AUTH id passwd")         # auth risc against Q
        self.mode(self.nick,"+x")                                           
        time.sleep(0.8)
        self.debug.info("[+] Joining " + self.channel + " ...")
        self.join()
        self.debug.info("[*] OK - Now processing\n")
        return None


    def on_ctcp(self,rawMsg):
        ltime = time.localtime()
        msg = []
        msg.append((' '.join(rawMsg[0].split(' ')[3:])[2:][:-1])) 
        sourceNick = rawMsg[0].split('!')[0][1:]

        self.debug.info("on_ctcp: Received CTCP '"+msg[0] +"' from '" + sourceNick+"'")

        if msg[0].lower() == "version":
            self._send("NOTICE "+sourceNick+ " :\001"+msg[0].upper()+' '+"risc v"+__version__+"\001")

        elif msg[0].lower() == "time":
            formatTime = str(ltime[1])+'/'+str(ltime[2])+'/'+str(ltime[0])+' '+str(ltime[3])+':'+str(ltime[4])+':'+str(ltime[5])
            self._send("NOTICE "+sourceNick+ " :\001"+msg[0].upper()+' '+formatTime+"\001")

        elif msg[0].lower() == "userinfo":
            self._send("NOTICE "+sourceNick+ " :\001"+msg[0].upper()+' '+"risc v"+__version__+" by Pr3acher @__Pr3__"+"\001")

        elif msg[0].lower() == "ping": 
            self._send("NOTICE "+sourceNick+ " :\001"+msg[0].upper()+' '+"PONG "+"\001")

        else:
            self._send("NOTICE "+sourceNick+ " :\001"+msg[0].upper()+' '+"Error: "+msg[0]+" CTCP command is not supported."+"\001")

        return None


    def set_option(self,section,option,value):
        try:
            self.cfg.read(INIPATH)
            self.cfg.set(section,option,value)
            self.cfg.write(open(INIPATH,"wb"))      # configparser only buffers the file ...
        except:
            self.debug.warning("set_option: exception caught")
            pass
        return None


    def get_last_threads(self):
        """
         returns the two last threads with their respective link and author in a string
        """
        try:
            dump = urllib2.urlopen(self.forum).read()
            parsed = BeautifulSoup(dump)
            allA = parsed.find_all('a') # get all <a> tags line

            # retrieve the thread' author
            allSpan = parsed.find_all('span')
            threadAuthor = []
            c = 0
            for span in allSpan:
                if re.search('by .+',str(span)):
                    span = str(span)
                    threadAuthor.append(span.split('>')[1].split('<')[0].strip()) # remove crazy html indent
                    c += 1
                    if c == 2: # we need the 2 threads' authors
                        break

            allAStr = []
            href = ""
            ret = ""
            found = 0
            skip = 1

            for a in allA:       # convert bs4 type shit to real str...
                allAStr.append(str(a))

        except:
            return COLOR['boldred']+"get_last_threads: Caugth exception: Couldn't retrieve last threads"+COLOR['rewind']

        c = 0
        for af in allAStr:
            if af.find('node-id') != -1 and af.find('post-link') != -1:
                c += 1

                if c == 1:
                    ret += COLOR['boldgreen']+af.split('>')[1][:-3]+COLOR['rewind']+' ('+COLOR['boldblue']+threadAuthor[0]+COLOR['rewind']+") - "

                if c == 3:
                    ret += COLOR['boldgreen']+af.split('>')[1][:-3]+COLOR['rewind']+' ('+COLOR['boldblue']+threadAuthor[1]+COLOR['rewind']+") - "

                elif c == 2 or c == 4:
                    href = af.split('"')[3] # get link
                    ret+=href+' , '
                    if c == 4:
                        self.set_option('rt','lastthreads',ret[:-3])
                        self.set_option('rt','lastthreadstime',int(time.time()))
                        return ret[:-3]

        return COLOR['boldred']+"get_last_threads: Couldn't retrieve last threads"+COLOR["rewind"]


    # XXX: FIX NEEDED: too slow
    def irc_is_on_channel(self,nick):
        """
        Checks whether a user-nick is on the channel, returns 0 if not, otherwise returns 1
        """
        try:
            self.sock.send('WHOIS '+nick+'\r\n')
            res=str(self.sock.recv(1024))
        except:
            self.debug.error('irc_is_on_channel: Exception caught')
            return 0
        if re.search(self.channel,res) == None or re.search(":No such nick",res):
            return 0
        return 1


    # XXX: FIX NEEDED: too slow
    def irc_is_authed(self,nick):
        """
        Check whether a user-nick is registered / has an account with quakenet, returns 0 if not, otherwise returns the account name
        """
        try:
            if not self.irc_is_on_channel(nick):
                return 0
            self.sock.send('WHOIS '+nick+'\r\n')
            res=str(self.sock.recv(1024))
        except:
            self.debug.error("irc_is_authed: Caught exception")
            return 0
        res = res.split(':')
        for i in range(len(res)):
            if re.search('is authed as',res[i]):
               tmp = self.list_clean(res[i-1].split(' '))
               auth = tmp[len(tmp)-1].strip()
               if nick.lower() == tmp[len(tmp)-2].strip().lower(): # some more precautions
                    return auth
        return 0


    # returns 0 if nick is not in the admin database, otherwise returns (auth,level)
    def irc_is_admin(self,nick):
        try:

            auth = self.irc_is_authed(nick)

            if not auth:
                return (0,0)

            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()

            cur.execute("""SELECT level FROM risc_irc_admins WHERE auth = '%s'""" % auth)

            con.commit()
            query = cur.fetchall()
            con.close()

        except:
            self.debug.critical("irc_is_admin: Exception. Rolling back db. Returning (0,0)")
            if con:
                con.rollback()
                con.close()
            return (auth,0)

        if len(query) != 1: # this makes the function fail if there're several records of the admin in the table
            return (auth,0)

        if query[0][0] == None: 
            return (auth,0)

        return (auth,int(query[0][0]))
    

    def cmd_iputgroup(self,source,msg):
        cleanIpg = self.list_clean(msg.split(' '))

        # check input
        if len(cleanIpg) != 3: #check global length
            return 0

        if len(cleanIpg[1]) > 19:
            return 0

        try:
            cleanIpg[2] = int(cleanIpg[2])
        except:
            return 0

        # check rights
        sourceAuth,sourceLevel = self.irc_is_admin(source)
        if not sourceAuth or sourceLevel != 100:
            return 0

        targetAuth,targetLevel = self.irc_is_admin(cleanIpg[1])
        if not targetAuth or (cleanIpg[2] not in self.args['!iputgroup'] and cleanIpg[2] != 0) or targetLevel == cleanIpg[2]:
            return 0

        try:
            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()

            if targetLevel in self.args["!iputgroup"] or cleanIpg[2] == 0: # if already admin, delete the record before.
                cur.execute("""DELETE FROM risc_irc_admins WHERE auth = '%s'""" % targetAuth)

            if cleanIpg[2] in self.args['!iputgroup']:
                cur.execute("""INSERT INTO risc_irc_admins(auth,level,addedOn,addedBy) VALUES('%s',%d,%d,'%s')""" % (targetAuth,cleanIpg[2],int(time.time()),sourceAuth))

            con.commit()
            con.close()

        except:
            self.debug.critical('cmd_iputgroup: Exception caught. Rolling back the db')
            if con:
                con.rollback()
                con.close()
            return 0

        if cleanIpg[2] == 0:
            return COLOR['boldgreen']+source+COLOR['rewind']+": User-auth "+COLOR['boldmagenta']+targetAuth+COLOR['rewind']+', '+COLOR['boldmagenta']+'admin'+COLOR['rewind']+'['+str(targetLevel)+'], is no more.'

        return COLOR['boldgreen']+source+COLOR['rewind']+": User-auth "+COLOR['boldmagenta']+targetAuth+COLOR['rewind']+" was successfully added to "+COLOR['boldmagenta']+'admin'+COLOR['rewind']+'['+str(cleanIpg[2])+'] group.'


    def cmd_ileveltest(self,msg0,sourceNick):
        cleanLt = self.list_clean(msg0.split(" "))
        testNick = sourceNick

        if len(cleanLt) > 2:
            self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+': Invalid arguments. Check !help ileveltest')
            return None

        sourceAuth,sourceLevel = self.irc_is_admin(sourceNick)

        if sourceLevel < self.commandLevels['!ileveltest'] or not sourceAuth:
            self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+": You cannot access this command. Check !help ileveltest")
            return None

        if len(cleanLt) == 2:
            testNick = cleanLt[1]

        targetAuth,targetLevel = self.irc_is_admin(testNick)

        if targetAuth and (targetLevel in self.args['!iputgroup'] or targetLevel == 100):
            if sourceNick.lower() == testNick.lower():
                self.privmsg(sourceNick,COLOR['boldgreen']+sourceNick+COLOR['rewind']+": You're a "+self.nick+" admin["+str(targetLevel)+'].')
            else:
                self.privmsg(sourceNick,COLOR['boldgreen']+sourceNick+COLOR['rewind']+": User "+COLOR['boldblue']+testNick+COLOR['rewind']+" is a "+self.nick+" admin["+str(targetLevel)+'].')
        else:
            if sourceNick.lower() == testNick.lower():
                self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+": You're not a "+self.nick+" admin.")
            else:
                self.privmsg(sourceNick,COLOR['boldgreen']+sourceNick+COLOR['rewind']+": User "+COLOR['boldblue']+testNick+COLOR['rewind']+' is not a '+self.nick+" admin.")
        return None


    def cmd_ishowadmins(self,msg0,sourceNick):
        cleanSA = self.list_clean(msg0.split(' '))
        try:
            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()

            cur.execute("""SELECT auth FROM risc_irc_admins""")

            admins = cur.fetchall()
            con.close()
        except Exception, e:
            self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+": Error: Couldn't retrieve the "+self.nick+" admin list")
            self.debug.critical( "cmd_ishowadmins: Exception: %s." % e)
            if con:
                con.rollback()
                con.close()
            return None

        if len (admins) == 0:
            self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+': The '+self.nick+' admin list is empty.')
            return None

        adminList = []
        for admin in admins:
            adminList.append(COLOR['boldgreen']+admin[0]+COLOR['rewind'])

        self.privmsg(sourceNick,self.nick+' admin list: '+', '.join(adminList))

        return None


    def cmd_hello(self,msg0,sourceNick):
        helloClean=self.list_clean(msg0.split(' '))
        lenHello = len(helloClean)

        if lenHello > 2:
            self.privmsg(sourceNick,'Invalid arguments. Check !help hello')
            return None

        if lenHello==1:
            self.privmsg(self.channel,COLOR["boldgreen"]+sourceNick+COLOR['rewind']+" says hi to "+self.channel)
            return None

        else:
            if len(helloClean[1]) > 28:
                self.privmsg(sourceNick,'Nick has too many chars')
                return None
            elif sourceNick.lower() == helloClean[1].lower():
                self.privmsg(self.channel,COLOR["boldgreen"]+sourceNick+COLOR['rewind']+" is feeling alone ...")
                return None
            else:
                if self.irc_is_on_channel(helloClean[1]) or helloClean[1].lower() == 'q': 
                    self.privmsg(self.channel,COLOR["boldgreen"]+sourceNick+COLOR['rewind']+" says hi to "+helloClean[1])
                else:
                    self.privmsg(sourceNick,"No such a nick")
        return None


    def cmd_ikick(self,msg0,sourceNick):
        cleanKick = self.list_clean(msg0.split(' '))
        lenKick = len(cleanKick)
        reason = sourceNick

        if lenKick < 2:
            self.privmsg(sourceNick,"Invalid arguments. Check !help kick.")
            return None

        if lenKick >= 3:
            reason = ''.join(cleanKick[2:])
        
        if re.search('@',cleanKick[1]):
            self.privmsg(sourceNick,"Can't kick using ident!")
            return None

        sourceAuth,sourceLevel = self.irc_is_admin(sourceNick)
        targetAuth,targetLevel = self.irc_is_admin(cleanKick[1])

        if sourceAuth and sourceLevel >= self.commandLevels['!ikick'] and sourceLevel > targetLevel:
            try:
                self.sock.send('KICK '+self.channel+' '+cleanKick[1]+' :'+reason+'\r\n')
            except:
                self.privmsg(sourceNick,"Couldn't kick the requested user!")
                self.debug.warning("cmd_ikick: Couldn't kick user!")
                return None
        else:
            self.privmsg(self.channel,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+": "+COLOR['boldred']+"You need to be admin["+str(self.commandLevels['!ikick'])+"] to access this command."+COLOR['rewind'])


    def cmd_sha1(self,msg0,sourceNick):
        cleanSha1Data = ''.join(msg0[6:]) # in case we have spaces in the string, they're taken into account

        if len(cleanSha1Data) > 150:
            self.privmsg(sourceNick,"Input too large.")
        else:
            try:
                sha1=hashlib.sha1(cleanSha1Data).hexdigest()
            except:
                self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+': '+COLOR['boldred']+'There was an error while computing. Check your input.'+COLOR['rewind'])
                return None
            self.privmsg(sourceNick,COLOR['boldgreen']+sourceNick+COLOR['rewind']+': '+sha1)
        return None


    def cmd_md5(self,msg0,sourceNick):
        cleanMd5Data = ''.join(msg0[5:]) 

        if len(cleanMd5Data) > 150:
            self.privmsg(sourceNick,"Input too large.")
        else:
            try:
                md5=hashlib.md5(cleanMd5Data).hexdigest()
            except:
                self.privmsg(sourceNick,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+': '+COLOR['boldred']+'There was an error while computing. Check your input.'+COLOR['rewind'])
                return None
            self.privmsg(sourceNick,COLOR['boldgreen']+sourceNick+COLOR['rewind']+': '+md5)
        return None


    def cmd_quit(self,msg0,sourceNick):
        sourceAuth,sourceLevel = self.irc_is_admin(sourceNick)
        if sourceAuth and sourceLevel >= self.commandLevels['!quit']:
            self.disconnect("%s killed me" % sourceNick)
            time.sleep(0.8)
            self.exit_process("Exiting now: %s" % sourceNick)
        else:
            self.privmsg(self.channel,COLOR['boldmagenta']+sourceNick+COLOR['rewind']+": "+COLOR['boldred']+"You need to be admin["+str(self.commandLevels["!quit"])+"] to access this command."+COLOR['rewind']) 
        return None


    def cmd_help(self, msg0, sourceNick):
        cleanHelp = self.list_clean(msg0.split(' '))
        lenCleanHelp=len(cleanHelp)

        if lenCleanHelp == 1:
            self.privmsg(sourceNick,HELP)
        elif lenCleanHelp == 2:
            self.privmsg(sourceNick,self.help_command('!'+cleanHelp[1]))
        else:
            self.privmsg(sourceNick,"Too many arguments. Check !help")
        return None


    def list_clean(self,list):
        ret = []
        for e in list:
            if e != '' and e != ' ':
                ret.append(e)
        return ret


    def get_dict_key(self,d,searchValue):
        for key in d:
            for val in d[key]:
                if val == searchValue.lower():
                    return key
        return 0


    def server_info(self,serv):
        self.cfg.read(INIPATH)
        ret = ''
        serv=serv.lower()

        if serv == 'all':
            for i in self.argAliases['servers']:
                fullIp = self.cfg.get('var',i).split(':')
                sv = Sv(fullIp[0],int(fullIp[1]))
                if not sv:
                    return COLOR['boldred']+"Error: Couldn't get the server status"+COLOR['rewind']
                if sv.clientsList == -1:
                    nbClients = 0
                else:
                    nbClients = len(sv.clientsList)

                ret += COLOR['boldgreen']+i+COLOR['rewind']+' : Players: '+COLOR['boldblue']+' '+str(nbClients)+COLOR['rewind']+'/'+str(sv.maxClients)+', map: '+COLOR['boldblue']+re.sub('\^[0-9]','',sv.mapName)+COLOR['rewind']+' - '
                del sv
            ret=ret[:-3]

        else:
            keyFromValue = self.get_dict_key(self.argAliases['servers'],serv) # get 'original' arg from alias
            if not keyFromValue:
                return 'Invalid argument. Check h !status'

            fullIp = self.cfg.get('var',keyFromValue).split(':')
            sv = Sv(fullIp[0],int(fullIp[1]))
            if not sv:
                return COLOR['boldred']+"Error: Couldn't get the server status"+COLOR['rewind']

            if sv.clientsList == -1:
                nbClients = 0
            else:
                nbClients = len(sv.clientsList)
            if int(sv.authNotoriety) >= 10:
                sv.authNotoriety = COLOR['boldblue']+'ON'+COLOR['rewind']
            else:
                sv.authNotoriety = COLOR['boldblue']+'OFF'+COLOR['rewind']
            if sv.allowVote == '1':
                sv.allowVote = COLOR['boldblue']+'ON'+COLOR['rewind']
            elif sv.allowVote == '0':
                sv.allowVote =COLOR['boldblue']+'OFF'+COLOR['rewind']

            ret = COLOR['boldgreen']+keyFromValue+COLOR['rewind']+' : Players: '+COLOR['boldblue']+' '+str(nbClients)+COLOR['rewind']+'/'+str(sv.maxClients)+', map: '+COLOR['boldblue']+re.sub('\^[0-9]','',sv.mapName)+COLOR['rewind']+', nextmap: '+COLOR['boldblue']+re.sub('\^[0-9]','',sv.nextMap) +COLOR['rewind']+', version: '+COLOR['boldblue']+sv.version+COLOR['rewind']+', auth: '+sv.authNotoriety+', vote: '+sv.allowVote
            del sv
        return ret


    def help_command(self,command):
        command = command.lower()

        if command in self.commands["!quit"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": Aliases: "+', '.join(self.commands["!quit"])+". Tells risc to leave. You need to be registered as admin["+str(self.commandLevels['!quit'])+"] with risc."

        elif command in self.commands["!lastthreads"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": Aliases: "+', '.join(self.commands["!lastthreads"])+". Displays the last two threads from forum.sniperjum.com."

        elif command in self.commands["!hello"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": <user> Aliases: "+', '.join(self.commands["!hello"])+". Simply says hi to user <user>. Use without <user> argument to target the channel."

        elif command in self.commands["!players"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+" <serverName>: Aliases: "+", ".join(self.commands["!players"])+". Shows all players on the <serverName> server. Available args/server-name: "+', '.join(self.args["!players"])

        elif command in self.commands["!search"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": <playerNick> <server> Aliases: "+', '.join(self.commands["!search"])+". Search for the player <playerNick> in the current server set if <server> is not specified, else it performs the search in the <server> server."

        elif command in self.commands["!ishowadmins"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": Aliases: "+', '.join(self.commands["!ishowadmins"])+". Shows all "+self.nick+" admins."

        elif command in self.commands["!base64"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+" <utf8String>: Aliases: "+', '.join(self.commands["!base64"])+". Returns a base64 encoded string from the utf-8 string <utf8String>."

        elif command in self.commands["!sha1"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+" <string>: Aliases: "+', '.join(self.commands["!sha1"])+". Returns the sha1 of the string <string>."

        elif command in self.commands["!ikick"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": <user> <reason> Aliases: "+', '.join(self.commands["!ikick"])+". Kicks the channel user <user>. You need to registered as admin["+str(self.commandLevels['!ikick'])+"] with risc. Also you can't kick another admin unless your level is strictly higher than his."

        elif command in self.commands["!ileveltest"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": <user> Aliases: "+', '.join(self.commands["!ileveltest"])+". Returns the level of the user <user> if he's registered as admin with risc. If you don't specify a <user> parameter, the command will return your level. You're required to be registered as admin["+str(self.commandLevels['!ileveltest'])+"] with PerBot to access this command."

        elif command in self.commands["!md5"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+" <string>: Aliases: "+', '.join(self.commands["!md5"])+". Returns the md5 of the string <string>."

        elif command in self.commands["!status"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+' <serverName>'+": Aliases: "+', '.join(self.commands["!status"])+". Diplays information about the <serverName> server. Available args/server-name: "+', '.join(self.args['!status'])

        elif command in self.commands["!iputgroup"]:
            return COLOR['boldgreen']+command +COLOR['rewind']+": <user> <level> Aliases: "+', '.join(self.commands["!iputgroup"])+". Set an admin level <level> to the user <user>. You need to be registered as admin["+ str(self.commandLevels['!iputgroup'])+"] with risc. <user> must have a quakenet account. Valid values for <level> include "+', '.join(str(x) for x in self.args['!iputgroup'])+'.'

        else:
            return "Command not found: "+COLOR['boldmagenta']+command+COLOR['rewind']


    def get_players(self,serverName,rawRet=0):
        """
        Returns all the player in the specified server
        """
        serverName = self.get_dict_key(self.argAliases['servers'],serverName.lower()) # handle arguments aliases
        ret = []
        if not serverName:
            return "Invalid arguments. Check !h players"

        self.cfg.read(INIPATH)
        fullIp = self.cfg.get('var',serverName).split(":")
        sv = Sv(fullIp[0],int(fullIp[1]))

        if not sv:
            return COLOR['boldred']+'Error retrieving :{Per}:'+serverName+' players'+COLOR['rewind']

        if sv.clients == 0 or sv.clientsList == -1:
            return serverName + ' server is currently empty.'

        usePings = False
        if len(sv.clientsPings) == len(sv.clientsList):
            usePings = True

        for i in range(len(sv.clientsList)):
            if usePings and sv.clientsPings[i] == '0':
                ping = COLOR['rewind']+' ('+COLOR['boldblue']+'BOT'+COLOR['rewind']+')'
            else:
                ping = ''

            ret.append(COLOR['boldgreen']+sv.clientsList[i]+COLOR['rewind']+ping)

        if rawRet:
            return ret
                                           # for some reason, sv.clients is innacurate here ...
        ret.sort()
        return 'Players on '+serverName+' ('+str(len(sv.clientsList))+'/'+str(sv.maxClients)+'): '+', '.join(ret)


    def search_player(self,player,rawRet=0):
        """
        Search for a player in the server set
        """
        if len(player) >= 30:
            return 'Player name has too many chars.'

        player = re.escape(player) # escape potentially dangerous chars (shouldn't happen tho ...)

        # get all players on all servers into a dict
        clients = {}
        pings = {}
        self.cfg.read(INIPATH)
        for server in self.args['!search']:
            fullIp = self.cfg.get('var',server).split(':')
            sv = Sv(fullIp[0],int(fullIp[1]))
            if not sv :
                return COLOR['boldred']+'An error occured while processing your command'+COLOR['rewind']
            if sv.clientsList != -1:
                clients.setdefault(server,sv.clientsList)
                pings.setdefault(server,sv.clientsPings)
            else:
                clients.setdefault(server,[''])

        if rawRet:
            return (clients,pings)

        # search for the player
        ret = []
        count = 0
        for sv in clients:
            for i in range(len(clients[sv])):
                if re.search(player.lower(),clients[sv][i].lower()):
                    count += 1
                    if len(pings[sv]) == len(clients[sv]):
                        if pings[sv][i] == '0':
                            ret.append(COLOR['boldgreen']+clients[sv][i]+COLOR['rewind']+' ('+COLOR['boldblue']+'BOT'+COLOR['rewind']+','+COLOR['boldblue']+' '+sv+COLOR['rewind']+')')
                        else:
                            ret.append(COLOR['boldgreen']+clients[sv][i]+COLOR['rewind']+' ('+COLOR['boldblue']+sv+COLOR['rewind']+')')
                    else:
                        ret.append(COLOR['boldgreen']+clients[sv][i]+COLOR['rewind']+' ('+COLOR['boldblue']+sv+COLOR['rewind']+')')

        lenRet = len(ret)
        if lenRet == 0:
            return COLOR['boldmagenta']+'No such a player in the server set.'+COLOR['rewind']
        elif lenRet == 1:
            return 'Found a player matching the request: '+ret[0]
        elif count > 15:
            return COLOR['boldmagenta']+"Too many players matching the request. Try to be more accurate."+COLOR['rewind']
        else:
            ret.sort()
            return 'Found '+str(count)+' players matching: '+', '.join(ret)


    def search_player_accurate(self,p,serv):
        """
        Search for a player in the server set
        """
        (cl,pings)=self.search_player(p,1)
        servKey = self.get_dict_key(self.argAliases["servers"],serv.lower())
        ret=[]
        count = 0

        if not servKey:
            return 'Invalid arguments: '+serv+'. Check !h search.'

        p = re.escape(p)

        if cl[servKey][0]=='' and len(cl[servKey][0])==1:
            return COLOR['boldmagenta']+'No such a player in the specified server.'+COLOR['rewind']

        usePings = 0
        isBot = COLOR['rewind']+' ('+COLOR['boldblue']+'BOT'+COLOR['rewind']+')'

        if len(cl[servKey]) == len(pings[servKey]):
            usePings = 1

        for i in range(len(cl[servKey])):
            if re.search(p.lower(),cl[servKey][i].lower()):
                count += 1
                if usePings:
                    if pings[servKey][i] == '0':
                        ret.append(COLOR['boldgreen']+cl[servKey][i]+isBot+COLOR['rewind'])
                    else:
                        ret.append(COLOR['boldgreen']+cl[servKey][i]+COLOR['rewind'])
                else:
                    ret.append(COLOR['boldgreen']+cl[servKey][i]+COLOR['rewind'])

        if count == 0: # 'not count' not giving the expecting result? ...
            return COLOR['boldmagenta']+'No such a player in the specified server.'+COLOR['rewind']
        elif count == 1:
            return 'Found a player matching the request in the '+COLOR['boldwhite']+servKey+COLOR['rewind']+' server: '+ret[0]
        else:
            ret.sort()
            return 'Found '+str(count)+' players matching the request in the '+COLOR['boldwhite']+servKey+COLOR['rewind']+' server: '+', '.join(ret)
    

##############################################################################################################
#                                                                                                            #
#                                       handle commands here                                                 #
#                                                                                                            #
##############################################################################################################


    def on_pubmsg(self,rawMsg):
        """
        Channel messages starting with the char '!' are processed here, if the command ever exists of course
        """
        global IS_GLOBAL_MSG
        cmdTime = time.time()
        sourceNick = rawMsg[0].split('!')[0][1:]
        msg = []
        msg.append((' '.join(rawMsg[0].split(' ')[3:])[1:])) # user full command

        global_msg = ''
        if IS_GLOBAL_MSG:
            global_msg = ' (global output)'

        self.debug.info("on_pubmsg: Received command '"+msg[0]+"' from '"+sourceNick+"'"+global_msg)

        # big switch where we handles received commands and eventually their args
        if msg[0].lower().split(' ')[0] in self.commands["!hello"]:
            self.cmd_hello(msg[0],sourceNick)
        
        elif msg[0].lower().split(' ')[0] in self.commands["!iputgroup"]:
            retCmdIpg =  self.cmd_iputgroup(sourceNick,msg[0])
            if not retCmdIpg: 
                self.privmsg(self.channel,COLOR['boldred']+"Failed. Check !h iputgroup"+COLOR['rewind'])
            else:
                self.privmsg(sourceNick,retCmdIpg)

        elif msg[0].lower().split(' ')[0] in self.commands["!ikick"]:
            self.cmd_ikick(msg[0],sourceNick)

        elif msg[0].lower().split(' ')[0] in self.commands["!ileveltest"]:
            self.cmd_ileveltest(msg[0],sourceNick)

        elif msg[0].lower().split(' ')[0] in self.commands["!search"]:
            cleanSearch = self.list_clean(msg[0].lower().split(' '))
            if len(cleanSearch) == 2:
                self.privmsg(sourceNick,self.search_player(cleanSearch[1]))
            elif len(cleanSearch) == 3:
                self.privmsg(sourceNick,self.search_player_accurate(cleanSearch[1].lower(),cleanSearch[2].lower()))
            else:
                self.privmsg(sourceNick,'Invalid arguments. Check !help search')

        elif msg[0].lower().strip().split(' ')[0] in self.commands["!base64"]:
            cleanB64 = self.list_clean(msg[0].split(' '))[0]
            cleanB64Data = ''.join(msg[0][len(cleanB64)+1:]) # in case we have spaces in the string
            if len(cleanB64Data) > 120:
                self.privmsg(sourceNick,"Input too large.")
            else:
                self.privmsg(sourceNick,base64.b64encode(bytearray(cleanB64Data,'utf-8')))

        elif msg[0].lower().strip().split(' ')[0] in self.commands["!sha1"]:
            self.cmd_sha1(msg[0],sourceNick)

        elif msg[0].lower().strip().split(' ')[0] in self.commands["!md5"]:
            self.cmd_md5(msg[0],sourceNick)

        elif msg[0].lower().split(' ')[0] in self.commands["!players"]:
            cleanPlayers = self.list_clean(msg[0].split(' '))
            if len(cleanPlayers) != 2:
                self.privmsg(sourceNick,"Invalid arguments. Check !h players")
            else:
                self.privmsg(sourceNick,self.get_players(cleanPlayers[1]))

        elif msg[0].lower().split(' ')[0] in self.commands["!status"]:
            cleanStatus = self.list_clean(msg[0].split(' '))
            lenStatus = len(cleanStatus)

            if lenStatus > 2:
                self.privmsg(sourceNick,"Too many arguments. Check !help status")
            elif lenStatus == 1:
                self.privmsg(sourceNick,self.server_info("all")) # consider "!status" == "!status all" 
            else:
                self.privmsg(sourceNick,self.server_info(cleanStatus[1]))

        elif msg[0].lower().strip() in self.commands["!lastthreads"]:
            try:
                self.cfg.read(INIPATH) # in case .ini has been updated, re-read it
                if self.cfg.has_option("rt","lastthreads") and self.cfg.has_option('rt',"lastthreadstime"):
                    cachedLtsTime = int(self.cfg.get("rt","lastthreadstime"))

                    if int(time.time())-cachedLtsTime <= self.refreshLastThreads:
                        cachedLts = self.cfg.get("rt","lastthreads")
                        self.privmsg(sourceNick,"Last threads: " + cachedLts) 
                        return None
            except Exception, e:
                self.debug.warning('on_pubmsg: lasthread exception: %s' %e)
                pass
            # no valid (time) cached query available; query again
            self.privmsg(sourceNick,"Last threads: " + self.get_last_threads())

        elif msg[0].lower().strip().split(' ')[0] in self.commands["!help"]:
            self.cmd_help(msg[0],sourceNick)

        elif msg[0].lower().strip() in self.commands["!ishowadmins"]:
            self.cmd_ishowadmins(msg[0],sourceNick)

        elif msg[0].lower().strip() in self.commands["!quit"]:
            self.cmd_quit(msg[0],sourceNick)

        return None

   
    # <client> <reason>
    def game_on_calladmin(self,sv,data):
        data_list = data.split('\r\n')
        player = data_list[0]
        reason = data_list[1]

        self.privmsg(self.channel,COLOR['boldwhite']+'['+COLOR['rewind']+COLOR['boldgreen']+sv+COLOR['rewind']+COLOR['boldwhite']+']'+\
                COLOR['rewind']+COLOR['boldblue']+' '+player+COLOR['rewind']+' requested an admin: '+COLOR['boldblue']+reason+COLOR['rewind'])
        return None


    # <map_name> <cl_count> <max_cl_count>
    def game_on_game_map_change(self,sv,data):
        data_list = data.split('\r\n')
        map_name = data_list[0]
        cl_count = data_list[1]
        max_cl_count = data_list[2]

        self.privmsg(self.channel,COLOR['boldwhite']+'['+COLOR['rewind']+COLOR['boldgreen']+sv+COLOR['rewind']+COLOR['boldwhite']+']'+\
                COLOR['rewind']+' map: '+COLOR['boldblue']+map_name+COLOR['rewind']+', players:'+COLOR['boldblue']+' '+cl_count+COLOR['rewind']+'/'+str(max_cl_count))
        return None


    # <admin> <admin_id> <client> <client_id> <reason=''>
    def game_on_client_kick(self,sv,data):
        data_list = data.split('\r\n')
        admin= data_list[0]
        admin_id = data_list[1]
        client = data_list[2]
        client_id = data_list[3]

        if data_list[4] == '':
            reason = COLOR['boldmagenta']+'No reason specified'+COLOR['rewind']
        else:
            reason = COLOR['boldblue']+data_list[4]+COLOR['rewind']

        self.privmsg(self.channel,COLOR['boldwhite']+'['+COLOR['rewind']+COLOR['boldgreen']+sv+COLOR['rewind']+COLOR['boldwhite']+']'+\
                COLOR['rewind']+COLOR['boldblue']+' '+admin+' @'+admin_id+COLOR['rewind']+' kicked'+COLOR['boldblue']+' '+client+' @'+client_id+COLOR['rewind']+': '+reason)
        return None


    # <admin> <admin_id> <client> <client_id> <duration_hour> <reason=''>
    def game_on_client_ban_temp(self,sv,data):
        data_list = data.split('\r\n')
        admin = data_list[0]
        admin_id = data_list[1]
        client = data_list[2]
        client_id = data_list[3]
        duration = data_list[4]

        if data_list[5] == '':
            reason = COLOR['boldmagenta']+'No reason specified'+COLOR['rewind']
        else:
            reason = COLOR['boldblue']+data_list[5]+COLOR['rewind']

        self.privmsg(self.channel,COLOR['boldwhite']+'['+COLOR['rewind']+COLOR['boldgreen']+sv+COLOR['rewind']+COLOR['boldwhite']+']'+\
                COLOR['rewind']+COLOR['boldblue']+' '+admin+' @'+admin_id+COLOR['rewind']+' banned'+COLOR['boldblue']+' '+client+' @'+\
                client_id+COLOR['rewind']+' for '+duration+'h : '+reason)
        return None


    # <admin> <admin_id> <client> <client_id> <reason=''>
    def game_on_client_ban(self,sv,data):
        data_list = data.split('\r\n')
        admin= data_list[0]
        admin_id = data_list[1]
        client = data_list[2]
        client_id = data_list[3]

        if data_list[4] == '':
            reason = COLOR['boldmagenta']+'No reason specified'+COLOR['rewind']
        else:
            reason = COLOR['boldblue']+data_list[4]+COLOR['rewind']

        self.privmsg(self.channel,COLOR['boldwhite']+'['+COLOR['rewind']+COLOR['boldgreen']+sv+COLOR['rewind']+COLOR['boldwhite']+']'+\
                COLOR['rewind']+COLOR['boldblue']+' '+admin+' @'+admin_id+COLOR['rewind']+' banned'+COLOR['boldblue']+' '+client+' @'+client_id+COLOR['rewind']+': '+reason)
        return None


    # using crlf separator on db data
    def game_watcher(self):
        try:
            # in case the bot is ran before the plugin, init tables
            for sv in self.sv_running:
                con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
                cur = con.cursor()
                cur.execute("""CREATE TABLE IF NOT EXISTS %s(ID INT AUTO_INCREMENT PRIMARY KEY,\
                                                   evt VARCHAR(40) NOT NULL DEFAULT '',\
                                                   data VARCHAR(255) NOT NULL DEFAULT '',\
                                                   time BIGINT NOT NULL DEFAULT 0,\
                                                   processed TINYINT NOT NULL DEFAULT 0)""" % ('risc_'+sv))
                con.commit()
                con.close()

            while 1:
                time.sleep(2)

                for sv in self.sv_running:
                    con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
                    cur = con.cursor()

                    cur.execute("""SELECT evt,data FROM %s WHERE processed = 0""" % ('risc_'+sv))
                    res = cur.fetchall()
                    len_res = len(res)
                    cur.execute("""UPDATE %s SET processed = 1 WHERE processed = 0""" % ('risc_'+sv))
                    con.commit()
                    con.close()

                    # don't process if there's too much in queue
                    if len_res >= 1 and len_res <= 4:
                        for row in res:
                            if row[0] == 'EVT_CALLADMIN':
                                self.game_on_calladmin(sv,row[1])
                            elif row[0] == 'EVT_GAME_MAP_CHANGE':
                                self.game_on_game_map_change(sv,row[1])
                            elif row[0] == 'EVT_CLIENT_KICK':
                                self.game_on_client_kick(sv,row[1])
                            elif row[0] == 'EVT_CLIENT_BAN_TEMP':
                                self.game_on_client_ban_temp(sv,row[1])
                            elif row[0] == 'EVT_CLIENT_BAN':
                                self.game_on_client_ban(sv,row[1])
                            else:
                                pass
        except Exception, e:
            self.debug.error('game_watcher: Exception cauhgt: %s - Passing' % e)
            pass


    def set_evt_callbacks(self):
        """
        Starts threads to watch specific events
        """
        self.debug.info( "[+] Setting and starting event callbacks")
        th=threading.Thread(None,self.game_watcher,None,(),None)
        th.start()
        return None


    def init_irc_admins(self):
        """
        Called on startup to init the irc admin table
        """
        # irc-auth of some admins who can handle the bot
        d = {'Pr3acher': 100,
             'vincentvega': 100,
             'NastyJoke': 100}

        con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
        cur = con.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS risc_irc_admins(ID INT NOT NULL AUTO_INCREMENT PRIMARY KEY,\
                                                                auth VARCHAR(20) NOT NULL DEFAULT '',\
                                                                level TINYINT NOT NULL DEFAULT 0,\
                                                                addedOn BIGINT NOT NULL DEFAULT 0,\
                                                                addedBy VARCHAR(20) NOT NULL DEFAULT '')""")

        for admin in d:
            cur.execute("""INSERT INTO risc_irc_admins(auth,level,addedOn,addedBy) VALUES('%s',%d,%d,'Pr3acher')""" % (admin,d[admin],int(time.time())))

        con.commit()
        con.close()
        return None


    def _send(self,data):
        self.sock.send(data+'\r\n')
        return None


    def join(self):
        self._send('JOIN '+self.channel)
        return None


    def disconnect(self,message="bye"):
        self._send("QUIT :%s" % message)
        return None


    def mode(self,target,command):
        self._send('MODE %s %s' % (target,command))
        return None

    
    def privmsg(self,target,msg):
        global IS_GLOBAL_MSG
        if IS_GLOBAL_MSG:
            target = self.channel
            IS_GLOBAL_MSG = 0
        self._send('PRIVMSG %s :%s' % (target, msg))
        return None


    def connect(self):
        self.sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # use TCP
        self.sock.connect((self.host,self.port))
        self._send("NICK " + self.nick)
        self._send("USER %s 0 * :%s" % (self.nick,self.nick))
        return None


    # decides whether its private msg or channel msg and call handler function
    def _on_privmsg(self,msg):
        global IS_GLOBAL_MSG 
        msgList=[]
        msgList.append(msg)

        l = msg.split(' ')
        target = l[2]                 # target == channel | pm 
        content = ' '.join(l[3:])[1:] # raw message from the user

        try:
            if re.search(b'[\0-\x0a]{1}[A-Z]+([\0-\x0a]){1}',bytearray(content,'utf-8')): # matches ctcp command
                self.on_ctcp(msgList)
                return None
        except Exception, e:
            self.debug.warning('_on_privmsg: Caught exception: %s -  Could be ascii conversion of non-ascii char (unicode) during regex process. Passing' %e)
            pass


        # only handle '!' | '@' prefixed messages
        if content[0] != '!' and content[0] != '@':
            return None

        if content[0] == '@':
            msgList[0] = re.sub(' :@',' :!',msgList[0])
            IS_GLOBAL_MSG = 1

        self.on_pubmsg(msgList) # this way we add support to pm cmd's


   ######################################################################################################################## 
   #                                                                                                                      #
   #                                                                                                                      #
   #                                   DISPTACH EVENT TO HANDLER FUNCTIONS                                                #
   #                                                                                                                      #
   #                                                                                                                      #
   ######################################################################################################################## 

    def dispatcher(self):
        onWelcome = 0
        while 1:
            res = self.sock.recv(512)

            # splits the buffer into lines, way more accurate, since the IRC protocol uses crlf separator
            for line in res.split('\r\n'): 

                if not line:
                    continue

                if re.search('PRIVMSG',line):
                    self._on_privmsg(line)

                if re.search('PING :',line):
                    self._send('PONG :'+line.split(':')[1])

                if re.search(':Welcome',line): # connected to server, we can now join the channel
                    if not onWelcome:          
                        self.on_welcome()
                        onWelcome = 1



if __name__ == '__main__':
    print "[+] Initializing ...."
    try:
        inst = Risc() # init config and stuff
        inst.start()
    except KeyboardInterrupt:
        print 'Caught <c-c>. Exiting.'
        inst.disconnect()
        inst.exit_process()
    except SystemExit:
        inst.disconnect()
        inst.exit_process("Caught SystemExit")
    except NameError:
        self.debug.error('Caught NameError exception on Risc.start(): Contact an admin to fix this asap. Passing')
        pass
    except Exception ,e:
        print 'Unhandled exception on Risc(): %s. Exiting.' %e
        inst.exit_process()

