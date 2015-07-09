#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Alfredo Miranda"
__version__ = "0.3"
__description__ = "Server for project of an IRC-based protocol to Interworking Protocols class."

import select
import socket
import sys
import signal
import os
from communication import send, receive, BUFFSIZE
from datetime import datetime, timedelta

from daemon import Daemon

WAIT_TIMEOUT = 5
LIMIT_TARGET = 5
LIMIT_CHANNEL = 10
LIMIT_CHANNEL_USER = 10
FORBID_CHARS_NICK = ':!@#$%'
FORBID_CHARS_CHAN = ':!@#$%'

DEBUG = True

class Channel(object):
    def __init__(self, name, owner, topic=""):
        self.name = name
        self.owner = owner
        self.topic = topic
        self.users = [owner]

class Client(object):
    def __init__(self, nickname, socket):
        self.nickname = nickname
        self.socket = socket
        self.channels = 0

class PIRCServer(object):
    def __init__(self, port=6667, backlog=5):
        self.amount_clients = 0
        self.clients_socket = {}
        self.clients_nick = {}
        

        self.amount_channels = 0
        self.channels = {}

        # Client Socket List (Output)
        self.outputs = []
        self.inputs = []
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', port))

        print('Listening to port {0}...'.format(port))
        self.socket.listen(backlog)

        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        print('Shutting down server...')

        for o in self.outputs:
            o.close()
   
        self.socket.close()

    def disconnect_client(self, socket, reason=""):
        socket.close()
        self.inputs.remove(socket)
        self.outputs.remove(socket)
        if socket in self.clients_socket:
            nickname = self.clients_socket[socket].nickname
            for c in self.channels.keys():
                #Force clients to leave channels.
                self.quit_chan(socket, c)
            self.amount_clients -= 1
            del self.clients_nick[self.clients_socket[socket].nickname]
            del self.clients_socket[socket]
            print("Client {0} has disconnected".format(nickname))
        
        return True

    def parser_data(self, data):
        command = ''
        arguments = []

        command = data.split(" ")[0]
        
        index = data.find(':')
        if index != -1:
            arguments = data[:index-1].split(" ")[1:]
            arguments.append(data[index:])
        else:
            arguments = data.split(" ")[1:]
        
        for i in range(len(arguments)):
             if arguments[i].startswith(":"):
                 arguments[i] = arguments[i][1:].split(" :")
             else:
                arguments[i] = arguments[i].split(",")
        print(command, arguments)
        
        return command, arguments

    def validate_grammar(self, data, type_data):
        if type_data == "nick":
            if len(data) > 20:
                return False
            for c in data:
                if c in FORBID_CHARS_NICK:
                    return False
            return True
        elif type_data == "channel":
            if not data[0] == "#":
                return False
            elif len(data) > 20:
                return False
            for c in data[1:]:
                if c in FORBID_CHARS_CHAN:
                    return False
            return True

    def commands(self, command, arguments, socket):
        #Receive command and argument, and send to responsible function.
        msg = ''
        dest = ''
        if command == "NICK":
            reply = self.nick(command, arguments, socket)
        elif command == "PRIVMSG":
            reply = self.message(command, arguments, socket)
        elif command == "JOIN":
            reply = self.join(command, arguments, socket)
        elif command == "LIST":
            reply = self.list_chan(command, arguments, socket)
        elif command == "PART":
            reply = self.part(command, arguments, socket)
        elif command == "TOPIC":
            reply = self.topic(command, arguments, socket)
        elif command == "KICK":
            reply = self.kick(command, arguments, socket)
        elif command == "QUIT":
            reply = self.quit_server(command, arguments, socket)
        elif command == "KILL":
            reply = self.kill(command, arguments, socket)
        else:
            msgs = []
            msg = '400 {0} :Unknown command'.format(command)
            dest = socket
            msgs.append([msg, dest])
            reply = msgs
        
        return reply
    
    def kill(self, command, arguments, socket):
        msgs = []
        nickname = self.clients_socket[socket].nickname
        
        if not arguments:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
            msgs.append([msg, dest])
        else:
            kill_nick = arguments[0][0]
            if socket.getpeername()[0] != "127.0.0.1":
                #ERR_NOPERMISSION
                dest = socket
                msg = "402 :No permission"
                msgs.append([msg, dest])
            else:
                if kill_nick in self.clients_nick:
                    dest = self.clients_nick[kill_nick].socket
                    for c in self.channels:
                        self.quit_chan(dest, c)
                    if len(arguments) > 1:
                        msg = "You were kicked because '{0}'.".format(arguments[1][0])
                    else:
                        msg = "You were kicked because 'No reason'."
                    send(dest, msg)
                    self.disconnect_client(self.clients_nick[kill_nick].socket)
                else:
                    #ERR_NOSUCHNICK
                    msg = "405 :No such nick"
                    dest = socket
                    msgs.append([msg, dest])
        
        return msgs
    
    def quit_server(self, command, arguments, socket):
        #When user is leaving the server, it sends a message to channels
        #and quits server.
        msgs = []
        nickname = self.clients_socket[socket].nickname
        
        if arguments:
            #Send user's message to channels.
            for c in self.channels:
                if nickname in self.channels[c]:
                    msg = "{0}".format(arguments[0][0])
                    msgs = self.message(command, [[chan_name], [msg]],socket)
        else:
            #Send default message to channels.
            for c in self.channels:
                if nickname in self.channels[c].users:
                    msg = "User {0} has disconnected from the server.".format(nickname)
                    msgs = self.message(command, [[c], [msg]],socket)
                    
        self.disconnect_client(socket)
        
        return msgs
    
    def kick(self, command, arguments, socket):
        #Kick a user from a channel.
        msgs = []
        if len(arguments) < 2:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 KICK :Not enough parameters"
            msgs.append([msg, dest])
        else:
            chan_name = arguments[0][0]
            nickname = self.clients_socket[socket].nickname
            kick_nick = arguments[1][0]
            dest = socket
            if chan_name in self.channels:
                #Verify if exist channel in list of channels.
                if nickname == self.channels[chan_name].owner:
                    #Allow just owner to kick users.
                    if kick_nick in self.channels[chan_name].users:
                        self.channels[chan_name].users.remove(kick_nick)
                        if len(arguments) > 2:
                            #Send message to other users on channel
                            msgs += self.message(command, [[chan_name], ["{0} has been kicked because '{1}'".format(kick_nick, arguments[2][0])]],socket)
                            msg = "PRIVMSG {0} :You have been kicked from {1} because '{2}'.".format(nickname, chan_name, arguments[2][0])
                            dest = self.clients_nick[kick_nick].socket
                        else:
                            #Send default message to other users on channel
                            msgs += self.message(command, [[chan_name], ["{0} has been kicked because 'No reason'".format(kick_nick)]],socket)
                            msg = "PRIVMSG {0} :You have been kicked from {1} because 'No reason'.".format(nickname, chan_name)
                            dest = self.clients_nick[kick_nick].socket
                    else:
                        #ERR_NOTONCHANNEL
                        msg = "408 {0} :Nickname is not on channel".format(kick_nick)
                else:
                    #ERR_NOPERMISSION
                    msg = "402"
            else:
                #ERR_NOSUCHCHANNEL
                msg = "407 {0} :No such channel".format(chan_name)
                    
            msgs.append([msg, dest])
        
        return msgs
        
    def topic(self, command, arguments, socket):
        msgs = []
        
        if not arguments:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
        else:
            chan_name = arguments[0][0]
            nickname = self.clients_socket[socket].nickname
            if len(arguments) == 1:
                if chan_name in self.channels:
                    dest = socket
                    if self.channels[chan_name].topic == "":
                        #RPL_NOTOPIC
                        msg = "304 {0} :No topic is set".format(chan_name)
                    else:
                        #RPL_TOPIC
                        msg = "305 {0} :{1}".format(chan_name, self.channels[chan_name].topic)
                else:
                    #ERR_NOSUCHCHANNEL
                    dest = socket
                    msg = "407 {0} :No such channel".format(chan_name)
            elif len(arguments) == 2:
                dest = socket
                if chan_name in self.channels:
                    if nickname == self.channels[chan_name].owner:
                        #CHANGE CHANNEL'S TOPIC
                        self.channels[chan_name].topic = arguments[1][0]
                        #Send message about changing to other users on channel
                        msgs += self.message("PRIVMSG", [[chan_name], ["Topic changed to '{0}'.".format(arguments[1][0])]], socket)
                        msg = "PRIVMSG {0} :You have changed the channel's topic to '{1}'.".format(chan_name, arguments[1][0])
                    else:
                        #ERR_NOPERMISSION
                        msg = "402"
                else:
                    #ERR_NOSUCHCHANNEL
                    msg = "407 {0} :No such channel".format(chan_name)
            
        msgs.append([msg, dest])
        return msgs
                
    def quit_chan(self, socket, chan_name):
        msgs = []
        nickname = self.clients_socket[socket].nickname
        if nickname in self.channels[chan_name].users:
            #Set message to other users and remove user from channel.
            msg = "User {0} has left the channel.".format(nickname)
            msgs = self.message('PRIVMSG', [[chan_name], [msg]], socket)
            msg = "You has left channel {0}.".format(chan_name)
            msgs.append([msg, dest])
            self.channels[chan_name].users.remove(nickname)
        
        if nickname == self.channels[chan_name].owner and len(self.channels[chan_name].users) > 0:
            #If who left the channel was channel owner, it is set someone else as owner.
            self.channels[chan_name].owner = self.channels[chan_name].users[0]
            sock = self.clients_nick[self.channels[chan_name].owner].socket
            msg = "PRIVMSG SERVER :You are the new owner of {0}\n\r".format(chan_name)
            send(sock, msg)
        
        if len(self.channels[chan_name].users) == 0:
            del self.channels[chan_name]
        
        self.clients_socket[socket].channels -= 1
        
        return msgs
    
    def part(self, command, arguments, socket):
        #Responsible for command PART, just make a verification and
        #call quit_chan()
        msgs = []
        
        if arguments:
            for c in arguments[0]:
                if c in self.channels:
                    if self.clients_socket[socket].nickname in self.channels[c].users:
                        msgs += self.quit_chan(socket, c)
                else:
                    #ERR_NOSUCHCHANNELL
                    msg = "407 {0} :No such channel".format(c)
                    dest = socket
        else:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
                
        return msgs
    
    def list_chan(self, command, arguments, socket):
        msgs = []

        if arguments:
            #Show specifics channels
            if len(arguments[0]) > 1:
                dest = socket
                #RPL_LISTSTART
                msg = "300"
                msgs.append([msg, dest])
                for c in arguments[0]:
                    if c in self.channels:
                        #RPL_LIST
                        msg = "301 {0} :{1}".format(self.channels[c].name, self.channels[c].topic)
                    else:
                        #RPL_NOSUCHCHANNEL
                        msg = "407 {0} :No such channel".format(c)
                        msgs = [[msg, dest]]
                        #If there is any channel which doesn't exist, it will return an error.
                        return msgs
                    msgs.append([msg, dest])
                #RPL_LISTEND
                msg = "303"
                msgs.append([msg, dest])
            else:
                #Show list of names.
                #RPL_LIST
                dest = socket
                msg = "300"
                msgs.append([msg, dest])
                chan_name = arguments[0][0]
                
                if chan_name in self.channels:
                    #RPL_LIST
                    msg = "301 {0} :{1}".format(chan_name, self.channels[chan_name].topic)
                    msgs.append([msg, dest])
                    for u in self.channels[chan_name].users:
                        if u == self.channels[chan_name].owner:
                            #RPL_LISTNAME OP
                            msg = "302 @{0}".format(u)
                        else:
                            #RPL_LISTNAME
                            msg = "302 {0}".format(u)
                        msgs.append([msg, dest])
                    #RPL_LISTEND
                    msg = "303"
                else:
                    #RPL_NOSUCHCHANNEL
                    msg = "407 {0} :No such channel".format(chan_name)
                msgs.append([msg, dest])
        else:
            #Show all channels
            dest = socket
            #RPL_LIST
            msg = "300"
            msgs.append([msg, dest])
            for c in self.channels:
                #RPL_LIST
                msg = "301 {0} :{1}".format(self.channels[c].name, self.channels[c].topic)
                msgs.append([msg, dest])
            #RPL_LISTEND
            msg = "303"
            msgs.append([msg, dest])
        
        return msgs
    
    def join(self, command, arguments, socket):
        msgs = []
        
        if not arguments:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
            msgs.append([msg, dest])
        else:
            #Join channels
            for c in arguments[0]:
                nick = self.clients_socket[socket].nickname
                if c in self.channels:
                    if not nick in self.channels[c].users:
                        if len(self.channels[c].users) <= LIMIT_CHANNEL:
                            if self.clients_socket[socket].channels <= LIMIT_CHANNEL_USER:
                                self.channels[c].users.append(nick)
                                msg = "PRIVMSG SERVER :You have joined to {0}.".format(c)
                                dest = socket
                                msgs.append([msg, dest])
                                msg = "PRIVMSG {0} :{1}.".format(c, self.channels[c].topic)
                                msgs.append([msg, dest])
                                self.clients_socket[socket].channels += 1
                                
                                for u in self.channels[c].users:
                                    if u == self.channels[c].owner:
                                        msg = "PRIVMSG {0} :=> @{1}".format(c, u)
                                    else:
                                        msg = "PRIVMSG {0} :=> {1}".format(c, u)
                                    msgs.append([msg, dest])
                                
                            else:
                                #ERR_TOOMANYCHANNELS
                                msg = "409 :You have joined too many channels"
                                dest = socket
                                msgs.append([msg, dest])
                        else:
                            #ERR_CHANNELISFULL
                            msg = "406 {0} :Cannot join channel".format(c)
                            dest = socket
                            msgs.append([msg, dest])
                else:
                    #Create and join channel
                    if self.validate_grammar(c, "channel"):
                        if self.clients_socket[socket].channels <= LIMIT_CHANNEL_USER:
                            self.channels[c] = Channel(c, nick)
                            self.amount_channels += 1
                            if len(arguments) == 2:
                                self.channels[c].topic = arguments[1][0]
                            msg = "PRIVMSG SERVER :You have created {0}.".format(c)
                            dest = socket
                            msgs.append([msg, dest])
                            msg = "PRIVMSG {0} :{1}".format(c, self.channels[c].topic)
                            msgs.append([msg, dest])
                            self.clients_socket[socket].channels += 1
                        else:
                            #ERR_TOOMANYCHANNELS
                            msg = "409 :You have joined too many channels"
                            dest = socket
                            msgs.append([msg, dest])
                    else:
                        #ERR_INVALIDNAME
                        msg = "403 {0} :Invalid name".format(arguments[0][0])
                        dest = socket
                        msgs.append([msg, dest])
        
        return msgs
    
    def message(self, command, arguments, socket):
        msgs = []
        
        if len(arguments) == 2:
            if len(arguments[1]) > 1 and len(arguments[1]) != len(arguments[0]):
                #ERR_NEEDMOREPARAMS
                dest = socket
                msg = "401 {0} :Not enough parameters".format(command)
            else:
                if len(arguments[0]) > LIMIT_TARGET:
                    #ERR_NEEDMOREPARAMS
                    dest = socket
                    msg = "411 :Too many targets"
                elif len(arguments[1]) == 1:
                    #Send a single message
                    for a in arguments[0]:
                        if a.startswith("#"):
                            #Send message to channel
                            if a in self.channels:
                                if self.clients_socket[socket].nickname in self.channels[a].users:
                                    for u in self.channels[a].users:
                                        if u != self.clients_socket[socket].nickname:
                                            msg = "PRIVMSG {0}@{1} :{2}".format(self.clients_socket[socket].nickname, a,arguments[1][0])
                                            dest = self.clients_nick[u].socket
                                            msgs.append([msg, dest])
                                else:
                                    #ERR_CANNOTSENDTOCHAN
                                    msg = "410 {0} :Cannot send to channel".format(a)
                                    dest = socket
                                    msgs.append([msg, dest])
                            else:
                                #ERR_NOSUCHCHANNEL
                                msg = "407 {0} :No such channel".format(a)
                                dest = socket
                                msgs.append([msg, dest])
                                        
                        else:
                            #Send message to a specif user
                            if not a == self.clients_socket[socket].nickname:
                                if a in self.clients_nick:
                                    msg = "PRIVMSG {0} :{1}".format(self.clients_socket[socket].nickname, arguments[1][0])
                                    dest = self.clients_nick[a].socket
                                else:
                                    #ERR_NOSUCHNICK
                                    msg = "405 :No such nick"
                                    dest = socket
                                msgs.append([msg, dest])
                else:
                    #Send different messages
                    for i in range(len(arguments[1])):
                        if arguments[0][i].startswith("#"):
                            #Send different messages to different channels
                            if arguments[0][i] in self.channels:
                                if self.clients_socket[socket].nickname in self.channels[arguments[0][i]].users:
                                    for u in self.channels[arguments[0][i]].users:
                                        if u != self.clients_socket[socket].nickname:
                                            msg = "PRIVMSG {0}@{1} :{2}".format(self.clients_socket[socket].nickname, arguments[0][i],arguments[1][i])
                                            dest = self.clients_nick[u].socket
                                            msgs.append([msg, dest])
                                else:
                                    #ERR_CANNOTSENDTOCHAN
                                    msg = "410 {0} :Cannot send to channel".format(a)
                                    dest = socket
                                    msgs.append([msg, dest])
                            else:
                                #ERR_NOSUCHCHANNEL
                                msg = "407 {0} :No such channel".format(a)
                                dest = socket
                                msgs.append([msg, dest])
                        else:
                            #Send different messages to different users
                            if not arguments[0][i] == self.clients_socket[socket].nickname:
                                if arguments[0][i] in self.clients_nick:
                                    msg = "PRIVMSG {0} :{1}".format(self.clients_socket[socket].nickname, arguments[1][i])
                                    dest = self.clients_nick[arguments[0][i]].socket
                                else:
                                    #ERR_NOSUCHNICK
                                    msg = "405 :No such nick"
                                    dest = socket
                                msgs.append([msg, dest])
        else:
            #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
                
        return msgs

    def nick(self, command, arguments, socket):
        msgs = []
        if not arguments:
           #ERR_NEEDMOREPARAMS
            dest = socket
            msg = "401 {0} :Not enough parameters".format(command)
        else:
            nickname = arguments[0][0]
            dest = socket
                
            if self.validate_grammar(nickname, "nick"):
                if nickname in self.clients_nick:
                    #ERR_NICKNAMEINUSE
                    msg = "404 {0} :Nickname is already in use".format(nickname)
                else:
                    if socket in self.clients_socket:
                        if nickname == "admin" and socket.getpeername()[0] != "127.0.0.1":
                            #ERR_NOPERMISSION
                            msg = "402 :No permission"
                        else:
                            #Verify and change nick.
                            old_nickname = self.clients_socket[socket].nickname
                            del self.clients_nick[old_nickname]
                            self.clients_socket[socket].nickname = nickname
                            self.clients_nick[nickname] = self.clients_socket[socket]
                            for c in self.channels:
                                if old_nickname in self.channels[c].users:
                                    index = self.channels[c].users.index(old_nickname)
                                    self.channels[c].users[index] = nickname
                                    if old_nickname == self.channels[c].owner:
                                        self.channels[c].owner = nickname
                            #RPL_NICKNAMECHANGED
                            msg = "306"
                    else:
                        if nickname == "admin" and socket.getpeername()[0] != "127.0.0.1":
                            #ERR_NOPERMISSION
                            msg = "402 :No permission"
                        else:
                            #Registering user
                            self.clients_socket[socket] = Client(nickname, socket)
                            self.clients_nick[nickname] = self.clients_socket[socket]
                    
                            #RPL_NICKNAMECHANGED
                            msg = "306"
            else:
                #ERR_NAMEINVALID
                msg = "403 {0} :Invalid name".format(nickname)
                dest = socket
        
        msgs.append([msg, dest])
        
        return msgs
                
    def loop(self):
        #Main function responsible for read inputs and accept connections.
        
        wait_list = {}
        self.inputs = [self.socket]

        while True:
            
            remove_wait_list = []

            try:
                inputready, outputready, exceptready = select.select(self.inputs, self.outputs, [])
            except select.error as e:
                break
            except socket.error as e:
                break

            for s in inputready:
                try:
                    if s == self.socket:
                        #Accept connections
                        clientsock, address = self.socket.accept()
                        wait_list[clientsock] = datetime.now()
                        self.outputs.append(clientsock)
                        self.inputs.append(clientsock)
                            
                    else:
                        #Verify other sockets, already accepted.
                        data = receive(s).strip("\n\r")[:BUFFSIZE-2]
                        if data:
                            command, arguments = self.parser_data(data)
                            reply = self.commands(command, arguments, s)
                            for msg, dest in reply:
                                data = msg + "\n\r"
                                if s in wait_list:
                                    #If client just connected, he is added on wait list, which is responsible
                                    #to keep tracking which users don't set their nick yet. After a while they
                                    #are disconnected.
                                    if command == "NICK":
                                        del wait_list[s]
                                        send(dest, data)
                                    else:
                                        msg = "PRIVMSG SERVER :You must try to use command NICK before\n\r"
                                        send(dest, msg)
                                        self.outputs.remove(s)
                                        self.inputs.remove(s)
                                        s.close()
                                        del wait_list[s]
                                
                                send(dest, data)
                        else:
                            #If there is no data, it means that client
                            #has closed connection.
                            try:
                                self.disconnect_client(s)
                            except BaseException as e:
                                pass
                except socket.error as e:
                    break
            
            for w in wait_list:
                #Track wait list
                if (datetime.now() - wait_list[w]).seconds > WAIT_TIMEOUT:
                    self.outputs.remove(w)
                    self.inputs.remove(w)
                    w.close()
                    remove_wait_list.append(w)
            
            for w in remove_wait_list:
                #Remove_Wait_List is responsible for track which users
                #set their nick and need to be removed from wait_list.
                del wait_list[w]
            
            del remove_wait_list
                        
class DaemonServer(Daemon):
    def run(self):
        self.main()

    def main(self):
        try:
            server = PIRCServer()

            # redirect standard file descriptors
            if not DEBUG:
                sys.stdout.flush()
                sys.stderr.flush()
                si = open(self.stdin, 'r')
                so = open(self.stdout, 'a+')
                se = open(self.stderr, 'a+', 0)
                os.dup2(si.fileno(), sys.stdin.fileno())
                os.dup2(so.fileno(), sys.stdout.fileno())
                os.dup2(se.fileno(), sys.stderr.fileno())
            
            server.loop()

        except KeyboardInterrupt:
            print("Stopping server...")

        except BaseException as err:
            print("Server can't be started!")
            print("ERROR: {0}".format(str(err)))

if __name__ == '__main__':
    daemon = DaemonServer('/var/run/pirc-server')
    if len(sys.argv) == 2:
        if sys.argv[1] == 'start':
            print("Starting...")
            daemon.start()
        elif sys.argv[1] == 'stop':
            print("Stopping...")
            daemon.stop()
        elif sys.argv[1] == 'restart':
            print("Restarting...")
            daemon.restart()
        else:
            print("Unknown command")
            print("Use: start|stop|restart")
            sys.exit(2)
    elif len(sys.argv) <= 1:
        print("It is missing arguments, use: ./server [start|stop|restart]")

