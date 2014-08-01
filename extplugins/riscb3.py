# -*- coding: utf-8 -*-

# TODO: 
#     - fix color for '/' in evt_game_map_change [OK]
#     - added event for kick / ban / tban / map change [OK]
#     - bug fix: get_last_calladmin [OK]
#     - minor bug fixes [OK]
#------ v1.1




import b3
import b3.events
import b3.plugin
import time
import MySQLdb as mysql


__author__ = 'Pr3acher'
__version__ = '1.1'


class Riscb3Plugin(b3.plugin.Plugin):
    requiresConfigFile = True


    def onLoadConfig(self):
        try:
            self.calladmin_threshold = int(self.config.get('calladmin','threshold'))
            self.db_host = self.config.get('db','host')
            self.db_user = self.config.get('db','user')
            self.db_passwd = self.config.get('db','passwd')
            self.db_name = self.config.get('db','name')
            self.db_table = 'risc_'+self.config.get('db','table')
            self.cmd_calladmin_level = int(self.config.get('calladmin','level'))
        except Exception, e:
            self.error('onLoadConfig: Error while loading config - Make sure all options are set and using a proper type')
        return None


    def onStartup(self):
        self.admin_plugin = self.console.getPlugin('admin')

        try:
            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS %s(ID INT AUTO_INCREMENT PRIMARY KEY,\
                                                   evt VARCHAR(40) NOT NULL DEFAULT '',\
                                                   data VARCHAR(255) NOT NULL DEFAULT '',\
                                                   time BIGINT NOT NULL DEFAULT 0,\
                                                   processed TINYINT NOT NULL DEFAULT 0)""" % (self.db_table))
            con.commit()
            con.close()
        except:
            self.error('onStartup: There was an error initializing db')
            if con:
                con.rollback()
                con.close()
            return None

        if not self.admin_plugin:
            self.error("Couldn't load admin plugin.")
            return None
        self.admin_plugin.registerCommand(self,"calladmin",self.cmd_calladmin_level,self.cmd_calladmin)

        self.registerEvent(b3.events.EVT_GAME_MAP_CHANGE)
        self.registerEvent(b3.events.EVT_CLIENT_KICK)
        self.registerEvent(b3.events.EVT_CLIENT_BAN_TEMP)
        self.registerEvent(b3.events.EVT_CLIENT_BAN)
        return None


    def _store_event(self,evt,data,t):
        """
        Store the event evt and it's data data into the database
        """
        try:
            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()

            cur.execute("""INSERT INTO %s(evt,data,time,processed) VALUES('%s','%s',%d,0)""" % (self.db_table,evt,data,int(t)))

            con.commit()
            con.close()
        except Exception, e:
            self.error('_store_event: Error storing event %s: %s - Passing' % (evt,e))
            if con: 
                con.close()
                pass
        return None


    def _get_last_calladmin(self):
        """
        returns the last time the calladmin cmd was issued (in seconds)
        """
        try:
            con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
            cur = con.cursor()

            cur.execute("""SELECT time FROM %s WHERE evt = 'EVT_CALLADMIN' AND ID = (SELECT MAX(ID) FROM %s)""" % (self.db_table,self.db_table))

            res = cur.fetchall()
            con.close()
        except:
            self.error('get_last_calladmin: Error retrieving last calladmin cmd time')
            if con:
                con.close()
            return 0

        if not len(res):
            return 0

        return int(res[0][0])


    def _timetostr(self,t):
        """
        Converts an ammount of time in seconds into a string (minutes & sec only)
        """
        self.debug('t=='+str(t))
        m = int(t / 60)
        s = int(t - (60 * m))

        m_str = 'minute'
        s_str = 'second'

        if m > 1:
            m_str += 's'
        if s > 1:
            s_str += 's'

        if m > 0:
            return str(m)+' '+m_str+' '+str(s)+' '+s_str
        else:
            return str(s)+' '+s_str


    def cmd_calladmin(self,data,client,cmd=None):
        """
        <reason> - Sends an admin request on the IRC channel
        """
        cur_time = int(time.time())
        len_data = len(data)
        last_calladmin = self._get_last_calladmin()

        if cur_time - last_calladmin > self.calladmin_threshold:
            if len_data <= 135 and len_data > 1:
                # <client> <reason>
                self._store_event('EVT_CALLADMIN',client.name+'\r\n'+data,cur_time)
                client.message('Admins have been made aware of your request.')
            else:
                client.message('Invalid reason: either no reason specified or too many characters.')
        else:
            client.message('You have to wait another %s before you can call an admin.' % (self._timetostr(self.calladmin_threshold-(cur_time-last_calladmin))))
        return None


    def on_map_change(self,event):
        cl_count = len(self.console.clients.getList())
        try:
            max_cl_count = self.console.getCvar("sv_maxclients").getInt()
        except TypeError:
            max_cl_count = 0

        # <map_name> <cl_count> <max_cl_count>
        self._store_event('EVT_GAME_MAP_CHANGE',event.data['new']+'\r\n'+str(cl_count)+'\r\n'+str(max_cl_count),event.time)
        return None


    def on_kick(self,event):
        con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
        cur = con.cursor()

        # get admin ID and name
        cur.execute("""SELECT clients.name, penalties.admin_id, penalties.client_id  FROM penalties INNER JOIN clients ON \
                    penalties.time_add = %d AND clients.id = penalties.admin_id AND penalties.type = 'Kick'""" % (event.time))

        query = cur.fetchall()
        con.close()

        if len(query) != 1:
            self.debug('on_kick: Something wrong in the query.')
            return None

        if len(query[0]) != 3:
            self.debug('on_kick: Something wrong in the query.')
            return None

        admin, admin_id, client_id = query[0][0], str(query[0][1]), str(query[0][2])
        reason = ''

        if len(event.data) >= 2:
            reason = event.data

        # <admin> <admin_id> <client> <client_id> <reason=''>
        self._store_event('EVT_CLIENT_KICK',admin+'\r\n'+admin_id+'\r\n'+event.client.name+'\r\n'+client_id+'\r\n'+reason,event.time)
        return None


    def on_tempban(self,event):
        con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
        cur = con.cursor()

        # get admin ID and name
        cur.execute("""SELECT clients.name, penalties.admin_id, penalties.client_id, penalties.duration FROM penalties INNER JOIN clients ON \
                    penalties.time_add = %d AND clients.id = penalties.admin_id AND penalties.type = 'TempBan'""" % (event.time))

        query = cur.fetchall()
        con.close()

        if len(query) != 1:
            self.debug('on_tempban: Something wrong in the query.')
            return None

        if len(query[0]) != 4:
            self.debug('on_tempban: Something wrong in the query.')
            return None

        admin, admin_id, client_id, duration = query[0][0], str(query[0][1]), str(query[0][2]), query[0][3]
        duration = str(round((float(duration) / 60.0),1)) # get the duration str in hours
        reason = ''

        if len(event.data['reason']) >= 2:
            reason = event.data['reason']

        # <admin> <admin_id> <client> <client_id> <duration_hour> <reason=''>
        self._store_event('EVT_CLIENT_BAN_TEMP',admin+'\r\n'+admin_id+'\r\n'+event.client.name+'\r\n'+client_id+'\r\n'+duration+'\r\n'+reason,event.time)
        return None


    def on_ban(self,event):
        con = mysql.connect(self.db_host,self.db_user,self.db_passwd,self.db_name)
        cur = con.cursor()

        # get admin ID and name
        cur.execute("""SELECT clients.name, penalties.admin_id, penalties.client_id  FROM penalties INNER JOIN clients ON \
                    penalties.time_add = %d AND clients.id = penalties.admin_id AND penalties.type = 'Ban'""" % (event.time))

        query = cur.fetchall()
        con.close()

        if len(query) != 1:
            self.debug('on_ban: Something wrong in the query.')
            return None

        if len(query[0]) != 3:
            self.debug('on_ban: Something wrong in the query.')
            return None

        admin, admin_id, client_id = query[0][0], str(query[0][1]), str(query[0][2])
        reason = ''

        if len(event.data['reason']) >= 2:
            reason = event.data['reason']

        # <admin> <admin_id> <client> <client_id> <reason=''>
        self._store_event('EVT_CLIENT_BAN',admin+'\r\n'+admin_id+'\r\n'+event.client.name+'\r\n'+client_id+'\r\n'+reason,event.time)
        return None


    def onEvent(self,event):
        try:

            if event.type == b3.events.EVT_GAME_MAP_CHANGE:
                self.on_map_change(event)

            elif event.type == b3.events.EVT_CLIENT_KICK:
                self.on_kick(event)

            elif event.type == b3.events.EVT_CLIENT_BAN_TEMP:
                self.on_tempban(event)

            elif event.type == b3.events.EVT_CLIENT_BAN:
                self.on_ban(event)

            else:
                self.dumpEvent(event)

        except Exception, e:
            self.error('onEvent: Could not handle a registered event: %s - Passing' % e)
            pass
        return None
