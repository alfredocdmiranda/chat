#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = "Alfredo Miranda"
__version__ = "0.3"
__description__ = "Client for project of an IRC-based protocol to Interworking Protocols class."

import socket
import sys
import select
from communication import send, receive

import time

BUFFSIZE = 512
PORT_DEFAULT = 6667

CMD = ["server", "nick", "msg", "join", "quit", "kill"]
ERR = ['400', '401', '402', '403', '404', '405', '406', '407', '408', '409', '410', '411', '412', '413']

class PIRClient(object):
    def __init__(self):
        self.connected = False
        self.flag = False
        self.prompt = "[foo]>"
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    def parser_cmd(self, cmd):
        #Receive line from the user's prompt and separete between
        #command and argument, before to send to server.
        command = ''
        arguments = []
        
        cmd = cmd[1:]
        command = cmd.split(" ")[0]
        
        
        index = cmd.find(':')
        
        if index != -1:
            arguments = cmd[:index-1].split(" ")[1:]
            arguments.append(cmd[index:])
        else:
            arguments = cmd.split(" ")[1:]
        
        for i in range(len(arguments)):
            if arguments[i].startswith(":"):
                arguments[i] = arguments[i][1:].split(" :")
            else:
                arguments[i] = arguments[i].split(",")
        
        return command, arguments
    
    def parser_data(self, data):
        #Receive line from the server and separate between command and arguments.
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

        return command, arguments
    
    def build_msg(self, cmd, arguments):
        #Create messages according to RFC to send to the server.
        if cmd == "nick":
            msg = "NICK"
            if len(arguments) == 1 and len(arguments[0]) == 1:
                self.change_nick = arguments[0][0]
                msg += " {0}\n\r".format(self.change_nick)
                return msg
            else:
                print("There is something wrong. Use '/nick <nick>'")
                return None
        elif cmd == "msg":
            msg = "PRIVMSG"
            if len(arguments) == 2:
                msg += " "
                for a in arguments[0]:
                    msg += a
                    if a is not arguments[0][-1]:
                        msg += ","
                
                msg += " "
                
                for a in arguments[1]:
                    msg += ':'
                    msg += a
                    
                    if a is not arguments[1][-1]:
                        msg += " "
                msg += "\n\r"
                return msg
        elif cmd == "join":
            msg = "JOIN"
            
            if arguments:
                msg += " "
                for a in arguments[0]:
                    msg += a
                    if a is not arguments[0][-1]:
                        msg += ","
                
                if len(arguments) == 2:
                    if len(arguments[1]) == len(arguments[0]):
                        for a in arguments[1]:
                            msg += " :{0}".format(a)
            msg += "\n\r"
            return msg
        elif cmd == "list":
            msg = "LIST"
            if arguments:
                msg += " "
                for a in arguments[0]:
                    msg += a
                    if a is not arguments[0][-1]:
                        msg += ","
            msg += "\n\r"
            return msg
        elif cmd == "part":
            msg = "PART"
            if arguments:
                msg += " "
                for a in arguments[0]:
                    msg += a
                    if a is not arguments[0][-1]:
                        msg += ","
            msg += "\n\r"
            return msg
        elif cmd == "topic":
            msg = "TOPIC"
            if arguments:
                msg += " "
                msg += arguments[0][0]
            
                if len(arguments) == 2:
                    msg += " :{0}".format(arguments[1][0])
            
            msg += "\n\r"
            return msg
        elif cmd == "kick":
            msg = "KICK"
            if arguments:
                msg += " "
                if len(arguments) == 3:
                    msg += "{0} {1} :{2}".format(arguments[0][0], arguments[1][0], arguments[2][0])
                elif len(arguments) == 2:
                    msg += "{0} {1}".format(arguments[0][0], arguments[1][0])
            msg += "\n\r"
            return msg
        elif cmd == "kill":
            msg = "KILL"
            if arguments:
                msg += " "
                msg += arguments[0][0]
                
                if len(arguments) > 1:
                    msg += " "
                    msg += arguments[1][0]
            msg += "\n\r"
            return msg
        elif cmd == "quit":
            msg = "QUIT"
            if arguments:
                msg += " "
                msg += arguments[0][0]
            msg += "\n\r"
            return msg
        
    def commands(self, command, arguments):
        #Proccess all possibles answers from the server and send to
        #function which is responsible for that answer.
        msg = ''
        dest = ''
        if command == "306":
            msg = self.nick(command, arguments)
        elif command == "PRIVMSG":
            msg = self.message(command, arguments)
        elif command in ['300', '301', '302', '303']:
            msg = self.list_chan(command, arguments)
        elif command in ['304', '305']:
            msg = self.list_topic(command, arguments)
        elif command in ERR:
            msg = self.err(command, arguments)
        
        return msg
    
    def err(self, command, arguments):
        #Define errors' behavior.
        
        reply = "\r"
        if command == '400':
            #ERR_UNKNOWNCOMMAND
            reply += "[ERR {1}]Command '{0}' unknown. ".format(arguments[0][0], command)
        elif command == '401':
            #ERR_NEEDMOREPARAMS
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '402':
            #ERR_NOPERMISSION
            reply += "[ERR {1}]{0}".format(arguments[0][0], command)
        elif command == '403':
            #ERR_INVALIDNAME
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '404':
             #ERR_NICKNAMEINUSE
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '405':
            #ERR_NOSUCHNICK
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '406':
            #ERR_CHANNELISFULL
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '407':
            #ERR_NOSUCHCHANNEL
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '408':
            #ERR_NOTONCHANNEL
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '409':
            #ERR_TOOMANYCHANNELS
            reply += "[ERR {1}]{0}".format(arguments[0][0], command)
        elif command == '410':
            #ERR_CANNOTSENDTOCHAN
            reply += "[ERR {2}]{0}: {1}. ".format(arguments[0][0], arguments[1][0], command)
        elif command == '411':
            #ERR_TOOMANYTARGETS
            reply += "[ERR {1}]{0}".format(arguments[0][0], command)
        
        return reply
    
    def list_topic(self, command, arguments):
        #It shows a channel and its topic.
        
        reply = "\r"
        if command == '304':
            reply += "{0}: No topic is set".format(arguments[0][0])
        elif command == '305':
            reply += "{0}: {1}".format(arguments[0][0], arguments[1][0])
    
    def list_chan(self, command, arguments):
        #It shows channels list.
        if command == '300':
            reply = "\rSTART LIST"
        elif command == '301':
            reply = "\r\t{0}\t{1}".format(arguments[0][0], arguments[1][0])
        elif command == '302':
            reply = "\r\t-> {0}".format(arguments[0][0])
        elif command == '303':
            reply = "\rEND LIST"
        elif command == '407':
            reply = "\r{0} {1}".format(arguments[0][0], arguments[1][0])
        
        return reply
    
    def message(self, command, arguments):
        #It prepares a message to show on the prompt.
        reply = "\r[{0}]>{1}".format(arguments[0][0], arguments[1][0])
        
        return reply
    
    def nick(self, command, arguments):
        #It changes nick.
        if command == "306":
            try:
                self.nickname = self.change_nick
                self.prompt = "[{0}]>".format(self.change_nick)
                del self.change_nick
                reply = "\rNick was changed."
            except BaseException:
                reply = None
        
        return reply
    
    def connect(self, args):
        #It is responsible for make the first contact and connection
        #with the server.
        if len(args) < 2:
            #Verify if there are all parameters for connection
            print("It is missing arguments")
            return False
        elif len(args) == 2:
            server = args[0][0]
            nickname = args[1][0]
            port = PORT_DEFAULT
        elif len(args) == 3:
            server = args[0][0]
            nickname = args[1][0]
            port = args[2][0]
        
        try:
            self.socket.connect((server, port))
            msg = "NICK {0}\n\r".format(nickname)
            send(self.socket, msg)
            data = receive(self.socket).strip("\n\r")
            command, arguments = self.parser_data(data)
            if command in ERR:
                command, arguments = self.parser_data(data)
                msg = self.commands(command, arguments)
                raise BaseException(msg)
            self.nickname = nickname
            self.prompt = "[{0}]>".format(nickname)
            self.connected = True
            print("You are connect to {0}.".format(server))
        except socket.error as e:
            self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print('Could not connect to chat server {0} at port {1}'.format(server, port))
            return False
        except BaseException as e:
            self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if msg:
                sys.stdout.write(str(e) + '\n\r')
            else:
                sys.stdout.write('\r')
            sys.stdout.flush()
            return False
        
        return True
        
    def loop(self):
        #Main function which read sockets and prompts.
        while not self.connected:
            #If not connected, wait until you digit /server
            try:
                sys.stdout.write(self.prompt)
                sys.stdout.flush()
                data = sys.stdin.readline().strip()
                if data:
                    if data.startswith("/"):
                        cmd, arguments = self.parser_cmd(data)
                        if cmd == 'server':
                            self.connect(arguments)
                        else:
                            print("You must connect to a server first. Use '/server <server> <nickname> [<port>]'.")
            except KeyboardInterrupt:
                sys.exit(1)

        while not self.flag:
            try:
                sys.stdout.write(self.prompt)
                sys.stdout.flush()

                # Wait for input from stdin & socket
                inputready, outputready,exceptrdy = select.select([0, self.socket], [],[])

                for i in inputready:
                    if i == 0:
                        #Get data from STDIN.
                        data = sys.stdin.readline().strip()
                        if data and data.startswith("/"):
                            cmd, arguments = self.parser_cmd(data)
                            msg = self.build_msg(cmd, arguments)
                            if msg:
                                send(self.socket, msg)
                    elif i == self.socket:
                        #Verify if socket is enable and receive data
                        data = receive(self.socket).strip("\n\r")
                        if data:
                            command, arguments = self.parser_data(data)
                            msg = self.commands(command, arguments)
                            if msg:
                                sys.stdout.write(msg + '\n\r')
                            else:
                                sys.stdout.write('\r')
                            sys.stdout.flush()
                        else:
                            #If socket is enable, but there is no data,
                            #it means that server closed connection.
                            print('Server disconnected.')
                            self.flag = True
                            break

            except KeyboardInterrupt:
                print('Exiting...')
                self.socket.close()
                break
            except socket.error as e:
                print(e)

if __name__ == '__main__':
    client = PIRClient()
    client.loop()
