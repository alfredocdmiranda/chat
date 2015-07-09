# -*- coding: utf-8 -*-

import socket

BUFFSIZE = 512

def send(channel, msg):
    data = msg.encode("UTF-8")
    #Fill up the message with blank spaces
    data += (" "*(512-len(data))).encode("UTF-8")
    channel.send(data)
    
    return True

def receive(channel):
    data = channel.recv(BUFFSIZE)
    data = data.decode('UTF-8')
    index = data.find('\n\r')
    data = data[0:index]

    return data
